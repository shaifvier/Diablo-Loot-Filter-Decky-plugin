export const styles = `
.d4-viewer { position:fixed; inset:0; z-index:100; background:#101923; color:#edf0f4; box-sizing:border-box; display:flex; flex-direction:column; padding:64px 32px 58px; font-size:16px; }
.d4-viewer * { box-sizing:border-box; }
.d4-viewer h1 { font-size:26px; margin:0 0 5px; color:#edc68c; }
.d4-viewer h2 { font-size:17px; color:#edc68c; margin:0 0 12px; }
.d4-viewer p { margin:6px 0 12px; line-height:1.5; }
.d4-muted { color:#aebccb; font-size:13px; line-height:1.5; overflow-wrap:anywhere; }
.d4-row { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.d4-controls { display:flex; gap:12px; margin:14px 0; align-items:flex-end; flex-wrap:wrap; }
.d4-control { flex:1; min-width:160px; max-width:310px; }
.d4-control label { display:block; color:#aebccb; font-size:12px; margin:0 0 5px; text-transform:uppercase; }
.d4-button { min-height:38px !important; padding:7px 14px !important; width:auto !important; font-size:14px !important; }
.d4-tab { min-width:110px; }
.d4-tab-active { background:#655138 !important; color:#ffe1b1 !important; }
.d4-toolbar { border-top:1px solid #334153; padding-top:12px; display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:12px; }
.d4-workspace { flex:1; min-height:0; display:flex; gap:18px; }
.d4-main { flex:1; min-width:0; min-height:0; display:flex; flex-direction:column; }
.d4-side { flex:0 0 300px; border-left:1px solid #334153; padding-left:18px; overflow-y:auto; min-height:0; }
.d4-scroll { overflow:auto; min-height:0; flex:1; padding:3px 5px; }
.d4-card { background:#1a2635; border:1px solid #354459; padding:12px; margin:0 0 9px; border-radius:6px; line-height:1.45; overflow-wrap:anywhere; }
.d4-card-selected { border-color:#dfb878; background:#283345; }
.d4-native-focus, .d4-focus:focus { outline:2px solid #9bd7ff; outline-offset:-2px; }
.d4-node { position:absolute; padding:0; border:1px solid #69778a; background:#243348; color:#becbdb; border-radius:50%; display:flex; align-items:center; justify-content:center; line-height:1; cursor:pointer; }
.d4-node.allocated { background:#b68b45; border-color:#ffe3a6; color:#141e2a; }
.d4-node.completed { background:#377e5d; color:#e4ffef; border-color:#83e0ab; }
.d4-node.selected, .d4-node.d4-native-focus, .d4-node:focus { outline:2px solid #83d5ff; outline-offset:2px; z-index:2; }
.d4-map { flex:1; min-height:0; overflow:auto; border:1px solid #334153; border-radius:8px; background:radial-gradient(ellipse at center,#1c2b3c,#101a27); }
.d4-map-layer { position:relative; transform-origin:top left; }
.d4-map svg { position:absolute; inset:0; pointer-events:none; }
.d4-note { background:#293444; color:#e4d4b8; padding:8px 12px; border-radius:5px; font-size:13px; margin:5px 0 10px; }
.d4-error { color:#ffb4a8; }
.d4-footer { border-top:1px solid #334153; padding-top:10px; margin-top:12px; font-size:12px; color:#b8c6d6; }
.d4-sheet-backdrop { position:absolute; inset:0; background:#060d17cf; display:flex; align-items:center; justify-content:center; z-index:10; padding:24px; }
.d4-sheet { width:min(650px,100%); max-height:calc(100vh - 130px); background:#172333; border:1px solid #6a7890; border-radius:10px; padding:24px; display:flex; flex-direction:column; overflow:auto; }
.d4-sheet h2 { font-size:22px; }
@media(max-width:1400px) { .d4-viewer { padding:60px 24px 54px; font-size:14px; } .d4-viewer h1 { font-size:23px; } .d4-side { flex-basis:260px; } .d4-controls { margin:10px 0; } }
`;
