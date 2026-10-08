"""Current Maxroll reference fixtures; geometry and independent durable checklists."""
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.providers import GAME_URL
from backend.service import LootService, Store
from backend.viewer import GAME_TTL, Normalizer, ViewerService, rotate, seed_preview

FIXTURES = Path(__file__).parent / 'fixtures' / 'viewer'
GAME = json.loads((FIXTURES / 'game.json').read_text())
BUILDS = {bid: json.loads((FIXTURES / (bid + '.json')).read_text()) for bid in ('xf9um40q', 'nq4dbn0q')}


class Client:
    def __init__(self):
        self.offline = False
        self.calls = 0

    def json(self, url):
        self.calls += 1
        if self.offline:
            raise OSError('Offline')
        assert url == GAME_URL
        return copy.deepcopy(GAME)


class NormalizerTest(unittest.TestCase):
    def test_every_blood_wave_and_rain_of_arrows_variant_agrees_with_lists(self):
        for bid, build in BUILDS.items():
            for vi, variant in enumerate(build['data']['profiles']):
                with self.subTest(build=bid, variant=vi):
                    ref = Normalizer(GAME).reference(build, vi)
                    self.assertEqual(ref['variantName'], variant['name'])
                    self.assertNotIn('data', ref)  # Only this variant's projection crosses the API.
                    self.assertEqual(len(ref['skills']['steps']), len(variant['skillTree']['steps']))
                    for step, raw in zip(ref['skills']['steps'], variant['skillTree']['steps']):
                        actual = {n['id']: n['rank'] for n in step['allocations']}
                        self.assertEqual(actual, {str(k): v for k, v in raw['data'].items() if v > 0})
                        self.assertEqual({n['id'] for n in step['nodes'] if n['allocated']}, set(actual))
                        ids = {n['id'] for n in step['nodes']}
                        self.assertTrue(all(e['from'] in ids and e['to'] in ids for e in step['connections']))
                    self.assertEqual([s['name'] for s in ref['paragon']['steps']], [s['name'] for s in variant['paragon']['steps']])
                    for step, source in zip(ref['paragon']['steps'], variant['paragon']['steps']):
                        for order, (board, raw) in enumerate(zip(step['boards'], source['data']), 1):
                            self.assertEqual(board['order'], order)
                            self.assertEqual(board['rotation'], raw['rotation'])
                            self.assertEqual(board['glyph']['level'], raw.get('glyphLevel'))
                            self.assertEqual(board['glyph']['name'], GAME['paragonGlyphs'].get(raw.get('glyph'), {}).get('name', 'No glyph'))
                            allocated = {str(k) for k, v in raw['nodes'].items() if v > 0}
                            self.assertEqual({n['id'] for n in board['allocations']}, allocated)
                            self.assertEqual({n['id'] for n in board['nodes'] if n['allocated']}, allocated)
                            width = board['width']
                            for n in board['nodes']:
                                ni = int(n['id'])
                                x, y = rotate(ni % width, ni // width, width, raw['rotation'])
                                self.assertEqual((n['x'], n['y']), (x * 24, y * 24))
                            for edge in board['connections']:
                                a, b = int(edge['from']), int(edge['to'])
                                self.assertTrue(b == a + width or (b == a + 1 and a // width == b // width))

    def test_common_stat_nodes_have_readable_names(self):
        ref = Normalizer(GAME).reference(BUILDS['xf9um40q'], 2)
        nodes = ref['paragon']['steps'][2]['boards'][0]['nodes']
        self.assertTrue(any(n['name'] == 'Willpower' for n in nodes))
        self.assertTrue(any(n['name'] == 'Strength' for n in nodes))

    def test_clockwise_rotation_zero_based_index(self):
        self.assertEqual([rotate(1, 0, 3, r) for r in range(4)], [(1, 0), (2, 1), (1, 2), (0, 1)])

    def test_rank_and_upgrade_are_not_clamped_to_five(self):
        build = copy.deepcopy(BUILDS['xf9um40q'])
        game = copy.deepcopy(GAME)
        node = next(n for n in game['skillTrees'][game['classes']['4']['tree']]['nodes']
                    if game['skillTreeRewards'].get(n.get('rewardId'), {}).get('type') == 1)
        reward = game['skillTreeRewards'][node['rewardId']]
        upgrade = next(m for m in game['skills'][reward['power']]['mods'] if m['id'] == reward['mod'])
        upgrade['desc'] = '{c_magic}Upgrade{reset} grants [math()] power.'
        build['data']['profiles'][0]['skillTree']['steps'][0]['data'][str(node['id'])] = 15
        ref = Normalizer(game).reference(build, 0)
        row = next(n for n in ref['skills']['steps'][0]['allocations'] if n['id'] == str(node['id']))
        self.assertEqual(row['rank'], 15)
        self.assertEqual(row['name'], upgrade['name'])
        self.assertEqual(row['kind'], 'Upgrade')
        self.assertEqual(row['description'], 'Upgrade grants … power.')

    def test_missing_mappings_remain_visible_with_list_fallback(self):
        build = copy.deepcopy(BUILDS['xf9um40q'])
        v = build['data']['profiles'][0]
        v['skillTree']['steps'][0]['data']['999999'] = 2
        v['paragon']['steps'][0]['data'][0]['nodes']['999999'] = 1
        normalizer = Normalizer({})
        ref = normalizer.reference(build, 0)
        self.assertFalse(ref['skills']['steps'][0]['nodes'])
        self.assertFalse(ref['paragon']['steps'][0]['boards'][0]['nodes'])
        self.assertTrue(any(n['id'] == '999999' for n in ref['skills']['steps'][0]['allocations']))
        self.assertTrue(any(n['id'] == '999999' for n in ref['paragon']['steps'][0]['boards'][0]['allocations']))
        self.assertTrue(any('geometry' in d for d in ref['diagnostics']))
        self.assertTrue(any('(identifier)' in i['name'] for i in ref['gear']))

    def test_natural_and_tempering_are_separate(self):
        build = copy.deepcopy(BUILDS['xf9um40q'])
        v = build['data']['profiles'][0]
        item = build['data']['items'][str(next(iter(v['items'].values())))]
        item['explicits'] = [{'nid': 999901, 'values': [12], 'greater': True}]
        item['tempered'] = [{'nid': 999902, 'values': [20]}]
        gear = Normalizer(GAME).reference(build, 0)['gear'][0]
        self.assertIn('999901', gear['natural'][0]['name'])
        self.assertIn('999902', gear['tempered'][0]['name'])
        self.assertTrue(gear['natural'][0]['greater'])


class ViewerServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.client = Client()
        self.loot = LootService(root / 'cache', self.client)
        for bid, build in BUILDS.items():
            self.loot.store.write('build-' + bid, build)
        self.viewer = ViewerService(self.loot, root / 'viewer')
        self.char = self.viewer.save_character(None, 'Necromancer')

    def tearDown(self):
        self.temp.cleanup()

    def keys(self, variant=0, step=0):
        ref = self.viewer.get_reference('xf9um40q', variant)
        return [n['key'] for b in ref['paragon']['steps'][step]['boards'] for n in b['allocations']]

    def get(self, char=None, variant=0, step=0):
        return self.viewer.get_progress(char or self.char['id'], 'xf9um40q', variant, step)

    def save(self, keys, char=None, variant=0, step=0):
        return self.viewer.set_progress(char or self.char['id'], 'xf9um40q', variant, step, keys)

    def test_named_characters_variants_and_steps_are_independent(self):
        second = self.viewer.save_character(None, 'Alt')
        keys = self.keys()
        self.save(keys[:2])
        self.assertEqual(len(self.get()['completed']), 2)
        self.assertFalse(self.get(second['id'])['completed'])
        self.assertFalse(self.get(variant=1)['completed'])
        self.assertFalse(self.get(step=1)['completed'])
        self.assertFalse(self.viewer.get_progress(self.char['id'], 'nq4dbn0q', 0, 0)['completed'])
        self.viewer.save_character(second['id'], 'Renamed')
        self.assertEqual(len(self.viewer.list_characters()), 2)
        self.assertEqual(self.viewer.list_characters()[1]['name'], 'Renamed')

    def test_persist_restart_reset_and_delete(self):
        keys = self.keys()
        self.save(keys[:3])
        self.viewer = ViewerService(self.loot, self.viewer.store.path)
        self.assertEqual(set(self.get()['completed']), set(keys[:3]))
        self.save([])
        self.assertFalse(self.get()['completed'])
        self.viewer.delete_character(self.char['id'])
        self.assertFalse(self.viewer.list_characters())
        self.assertFalse(self.viewer.store.read('progress'))

    def test_refresh_reconciles_common_nodes_and_requires_review(self):
        keys = self.keys()
        self.save(keys[:2])
        build = copy.deepcopy(BUILDS['xf9um40q'])
        board_id, nid = keys[0].rsplit('/', 1)
        board = next(b for b in build['data']['profiles'][0]['paragon']['steps'][0]['data'] if b['id'] == board_id.rsplit(':', 1)[0])
        del board['nodes'][nid]
        board['rotation'] = (board['rotation'] + 1) % 4
        self.loot.store.write('build-xf9um40q', build)
        progress = self.get()
        self.assertEqual(progress['completed'], keys[1:2])
        self.assertTrue(progress['needsReview'])
        self.assertTrue(self.get()['needsReview'])
        self.assertFalse(self.save(progress['completed'])['needsReview'])

    def test_offline_24_hour_game_cache_and_saved_projection(self):
        ref = self.viewer.get_reference('xf9um40q', 0)
        self.client.offline = True
        self.assertFalse(self.viewer.get_reference('xf9um40q', 0)['stale'])
        self.assertEqual(self.client.calls, 1)
        cached = self.viewer.store.read('game-data')
        cached['timestamp'] = time.time() - GAME_TTL - 1
        self.viewer.store.write('game-data', cached)
        self.viewer = ViewerService(self.loot, self.viewer.store.path)
        stale = self.viewer.get_reference('xf9um40q', 0)
        self.assertTrue(stale['stale'])
        self.assertEqual(stale['paragon'], ref['paragon'])
        self.viewer.store.path.joinpath('game-data.json').unlink()
        self.viewer = ViewerService(self.loot, self.viewer.store.path)
        projected = self.viewer.get_reference('xf9um40q', 0)
        self.assertTrue(projected['stale'])
        self.assertEqual(projected['skills'], ref['skills'])
        self.save(self.keys()[:1])  # Reference alone still supports the manual checklist offline.

    def test_save_failure_leaves_previous_atomic_file_intact(self):
        keys = self.keys()
        self.save(keys[:1])
        before = self.viewer.store.path.joinpath('progress.json').read_bytes()
        with patch('backend.service.os.replace', side_effect=OSError('Disk full')):
            with self.assertRaisesRegex(OSError, 'Disk full'):
                self.save(keys[:2])
        self.assertEqual(self.viewer.store.path.joinpath('progress.json').read_bytes(), before)
        self.assertEqual(self.get()['completed'], sorted(keys[:1]))

    def test_invalid_ids_nodes_and_variants_are_rejected(self):
        for vi in (-1, 100, True, '0'):
            with self.subTest(variant=vi), self.assertRaises(ValueError):
                self.viewer.get_reference('xf9um40q', vi)
        with self.assertRaises(ValueError):
            self.viewer.get_reference('../credentials', 0)
        with self.assertRaises(ValueError):
            self.save(['not-allocated'])
        with self.assertRaises(ValueError):
            self.get(step=99)
        for name in ('', ' ' * 2, 'x' * 41):
            with self.assertRaises(ValueError):
                self.viewer.save_character(None, name)

    def test_seed_copies_cache_once_and_never_shares_writes(self):
        target = Path(self.temp.name) / 'preview-cache'
        before = {p.name: p.read_bytes() for p in self.loot.store.path.glob('*.json')}
        self.loot.store.write('characters', {'secret': 'Do not copy'})
        seed_preview(target, self.loot.store.path)
        self.assertFalse(target.joinpath('characters.json').exists())
        preview = Store(target)
        original = preview.read('build-xf9um40q')
        self.assertEqual(original, BUILDS['xf9um40q'])
        preview.write('build-xf9um40q', {'preview': True})
        seed_preview(target, self.loot.store.path)
        self.assertEqual(preview.read('build-xf9um40q'), {'preview': True})
        for name, data in before.items():
            self.assertEqual(self.loot.store.path.joinpath(name).read_bytes(), data)
        self.assertEqual(len(self.viewer.list_builds()), 2)


if __name__ == '__main__':
    unittest.main()
