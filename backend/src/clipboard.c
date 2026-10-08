/* Persistent X11 CLIPBOARD owner. D4 codes are ASCII, so STRING and UTF8 agree.
 * MIT, Copyright (c) 2026 shaifvier. Built against the system X11 ABI.
 */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 2 || argc > 3) { fprintf(stderr, "Usage: d4-clipboard :display [test-selection]\n"); return 2; }
    Display *d = XOpenDisplay(argv[1]);
    if (!d) { fprintf(stderr, "Cannot open X11 display\n"); return 1; }
    Window window = XCreateSimpleWindow(d, DefaultRootWindow(d), 0, 0, 1, 1, 0, 0, 0);
    Atom clipboard = XInternAtom(d, argc == 3 ? argv[2] : "CLIPBOARD", False);
    Atom targets = XInternAtom(d, "TARGETS", False);
    Atom utf8 = XInternAtom(d, "UTF8_STRING", False);
    Atom text = XInternAtom(d, "TEXT", False);
    Atom plain = XInternAtom(d, "text/plain;charset=utf-8", False);
    char *code = calloc(128001, 1);
    if (!code) { XCloseDisplay(d); return 1; }
    size_t length = 0;
    for (;;) {
        ssize_t count = read(STDIN_FILENO, code + length, 128001 - length);
        if (count < 0) { free(code); XCloseDisplay(d); return 1; }
        if (!count) break;
        length += (size_t)count;
        if (length > 128000) { free(code); XCloseDisplay(d); return 2; }
    }
    if (!length) { free(code); XCloseDisplay(d); return 2; }
    XSetSelectionOwner(d, clipboard, window, CurrentTime);
    XSync(d, False);
    if (XGetSelectionOwner(d, clipboard) != window) {
        fprintf(stderr, "Could not own clipboard\n"); free(code); XCloseDisplay(d); return 1;
    }
    puts("READY"); fflush(stdout);
    /* Ownership lasts until another copy operation or plugin unload. */
    for (;;) {
        XEvent event;
        XNextEvent(d, &event);
        if (event.type == SelectionClear) break;
        if (event.type != SelectionRequest) continue;
        XSelectionRequestEvent *request = &event.xselectionrequest;
        Atom property = request->property == None ? request->target : request->property;
        XSelectionEvent reply;
        memset(&reply, 0, sizeof(reply));
        reply.type = SelectionNotify;
        reply.display = d;
        reply.requestor = request->requestor;
        reply.selection = request->selection;
        reply.target = request->target;
        reply.time = request->time;
        reply.property = None;
        if (request->target == targets) {
            Atom supported[] = {targets, utf8, XA_STRING, text, plain};
            XChangeProperty(d, request->requestor, property, XA_ATOM, 32,
                            PropModeReplace, (unsigned char *)supported, 5);
            reply.property = property;
        } else if (request->target == utf8 || request->target == XA_STRING ||
                   request->target == text || request->target == plain) {
            Atom type = request->target == XA_STRING ? XA_STRING : utf8;
            XChangeProperty(d, request->requestor, property, type, 8,
                            PropModeReplace, (unsigned char *)code, (int)length);
            reply.property = property;
        }
        XSendEvent(d, request->requestor, False, 0, (XEvent *)&reply);
        XFlush(d);
    }
    free(code);
    XDestroyWindow(d, window);
    XCloseDisplay(d);
    return 0;
}
