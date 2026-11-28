"""Headless online-play test for Paperland Trails, on Ember Hollow (#hollow) only.

Two pages in one Chrome join the same room through NETKIT's same-browser transport
(BroadcastChannel), so no internet or matchmaking server is needed. Player B walks and
sends a radio (chat) message; player A must see B move and must receive the message.

Usage:  python3 tools/online-test/two_hikers.py [path/to/three.min.js] [path/to/GLTFLoader.js]
The shipped index.html is never changed: the test-only hook (window.__E) is injected
into the copy served to the browser.
"""
import http.server, json, os, socketserver, sys, threading, time
from playwright.sync_api import sync_playwright

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
THREE = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/threejs/build/three.min.js'
GLTF = sys.argv[2] if len(sys.argv) > 2 else '/home/claude/threejs/examples/js/loaders/GLTFLoader.js'
PORT = 8765
URL = f'http://localhost:{PORT}/index.html#hollow'
HOOK_AT = 'hud();requestAnimationFrame(frame);'
ROOM = 'pl-hollow1'
WALK_S = float(os.environ.get('WALK_S', '8'))  # software rendering is slow; hold W long enough for real frames

class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=REPO, **k)
    def log_message(self, *a): pass

def serve():
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def patched_html():
    src = open(os.path.join(REPO, 'index.html'), encoding='utf-8').read()
    i = src.rfind(HOOK_AT)
    assert i > 0, 'injection point not found'
    return src[:i] + 'window.__E=s=>eval(s);' + src[i:]

results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail else ''), flush=True)
    return ok

def main():
    srv = serve()
    html = patched_html()
    three, gltf = open(THREE, 'rb').read(), open(GLTF, 'rb').read()
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True,
                                args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                                      '--use-gl=angle', '--disable-background-timer-throttling',
                                      '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'])
        ctx = br.new_context(viewport={'width': 360, 'height': 225})

        def route(r):
            u = r.request.url
            if u.startswith(f'http://localhost:{PORT}/index.html'):
                return r.fulfill(status=200, content_type='text/html; charset=utf-8', body=html)
            if 'three.min.js' in u and 'localhost' not in u:
                return r.fulfill(status=200, content_type='application/javascript', body=three)
            if 'GLTFLoader' in u and 'localhost' not in u:
                return r.fulfill(status=200, content_type='application/javascript', body=gltf)
            if 'localhost' in u or u.startswith('data:') or u.startswith('blob:'):
                return r.continue_()
            return r.abort()          # everything else on the internet: blocked, keeps the test offline
        ctx.route('**/*', route)

        errs = {}
        def open_player(tag):
            p = ctx.new_page(); errs[tag] = []
            p.on('pageerror', lambda e: errs[tag].append(str(e)[:200]))
            p.goto(URL, wait_until='load', timeout=120000)
            p.wait_for_function('typeof window.__E==="function"', timeout=120000)
            p.evaluate("()=>{const i=document.getElementById('rwIntro');if(i)i.remove();const b=document.getElementById('startBtn');if(b)b.click();}")
            return p

        t0 = time.time()
        A = open_player('A'); B = open_player('B')
        print(f'loaded both pages in {time.time()-t0:.1f}s', flush=True)
        E = lambda p, js: p.evaluate('s=>window.__E(s)', js)
        fps = lambda p: p.evaluate('()=>new Promise(r=>{let n=0;const t=performance.now();const f=()=>{n++;if(performance.now()-t<2000)requestAnimationFrame(f);else r(n/2)};requestAnimationFrame(f)})')
        print('frame rate  A', fps(A), ' B', fps(B), flush=True)

        # Guard: this must be Ember Hollow, never the full Oregon Wilds world.
        for tag, p in (('A', A), ('B', B)):
            m = E(p, 'JSON.stringify({MAP,WORLD,MAPKEY,LIM})')
            info = json.loads(m)
            if not check(f'{tag} is on Ember Hollow (small map)', info['MAPKEY'] == 'hollow' and info['WORLD'] is False, m):
                raise SystemExit('Wrong map loaded; stopping before testing on the full world.')

        # Join: A hosts, B joins, both on the same-browser transport.
        E(A, "NETKIT.config({transport:NETKIT_TRANSPORTS.local(),rate:12,joinWait:12000});"
             f"NET.name='Alder';window.__h=NETKIT.host({{code:'{ROOM}',name:'Alder',color:'#b5562f',maxPlayers:4,onHostLeave:'migrate',world:{{day:st.day,t:st.t,fuel:st.fuel}}}}).then(c=>window.__hc=c,e=>window.__he=String(e))")
        A.wait_for_function('()=>window.__E("NETKIT.inSession()")', timeout=10000)
        if os.environ.get('NKDEBUG'):
            B.evaluate(f"()=>{{window.__raw=[];new BroadcastChannel('paperland-{ROOM}').onmessage=e=>__raw.push(e.data.pkt.t+' '+(e.data.to||'*')+' '+JSON.stringify(e.data.pkt.p||e.data.pkt.k||'').slice(0,140))}}")
            time.sleep(2)
            print('raw seen by B before joining:', B.evaluate('__raw.slice(0,6)'))
        E(B, "NETKIT.config({transport:NETKIT_TRANSPORTS.local(),rate:12,joinWait:12000});"
             f"NET.name='Birch';NETKIT.join('{ROOM}',{{name:'Birch',color:'#3f7a8c',maxPlayers:4}}).then(()=>window.__jok=1,e=>window.__je=String(e))")
        try:
            B.wait_for_function('()=>window.__jok||window.__je', timeout=30000)
        except Exception: pass
        je = B.evaluate('window.__je||""')
        if not check('B joined A\'s room', not je and B.evaluate('!!window.__jok'), je):
            for tag, p in (('A', A), ('B', B)):
                print(tag, p.evaluate('()=>JSON.stringify({hc:window.__hc,he:window.__he,vis:document.visibilityState,bc:typeof BroadcastChannel})'),
                      E(p, 'JSON.stringify({inS:NETKIT.inSession(),host:NETKIT.isHost(),code:NETKIT.code(),pl:NETKIT.players().length})'), errs[tag][:3])
            if os.environ.get('NKDEBUG'): print('raw total', B.evaluate('__raw.length'), B.evaluate('__raw.slice(-8)'))
            raise SystemExit(1)
        A.wait_for_function('()=>window.__E("NETKIT.players().length")===2', timeout=10000)
        check('A sees 2 players', E(A, 'NETKIT.players().length') == 2, E(A, 'JSON.stringify(NETKIT.players().map(p=>p.name))'))
        check('B sees 2 players, A is host', E(B, 'NETKIT.players().some(p=>p.isHost&&p.name==="Alder")'),
              E(B, 'JSON.stringify(NETKIT.players().map(p=>[p.name,p.isHost]))'))

        # Avatars appear once the first position arrives.
        time.sleep(1.5)
        check('A draws an avatar for B', E(A, 'NET.others.size') == 1)

        # B walks forward for 2 s.
        AV = 'JSON.stringify([...NET.others.values()].map(o=>({x:o.x,z:o.z}))[0]||null)'
        b0 = json.loads(E(B, 'JSON.stringify({x:player.x,z:player.z})'))
        a0 = json.loads(E(A, AV))
        B.bring_to_front(); B.keyboard.down('KeyW'); time.sleep(WALK_S); B.keyboard.up('KeyW')
        b1 = json.loads(E(B, 'JSON.stringify({x:player.x,z:player.z})'))
        moved = ((b1['x']-b0['x'])**2 + (b1['z']-b0['z'])**2) ** 0.5
        check('B walked (game runs ~10x slow under software rendering)', moved > 0.2, f'{moved:.2f} m')
        time.sleep(4)  # network rate is 12/s, avatar eases in over ~0.5 s
        seen = json.loads(E(A, AV))
        amov = ((seen['x']-a0['x'])**2 + (seen['z']-a0['z'])**2) ** 0.5 if seen and a0 else 0
        check('A saw B\'s avatar move by the same amount', abs(amov - moved) < 0.1 and amov > 0.2, f'A saw {amov:.2f} m, B walked {moved:.2f} m')
        gap = ((seen['x']-b1['x'])**2 + (seen['z']-b1['z'])**2) ** 0.5 if seen else 99
        check('A sees B at B\'s new spot', gap < 0.3, f'gap {gap:.2f} m (B at {b1["x"]:.2f},{b1["z"]:.2f})')

        # B sends a radio message through the real chat form.
        E(B, "dockOpen('radio')"); time.sleep(0.3)
        B.fill('#dkChatIn', 'Hello from Birch at the hollow')
        B.evaluate("()=>document.getElementById('dkChatF').requestSubmit()")
        A.wait_for_function('()=>window.__E("CHAT.length")>0', timeout=5000)
        got = E(A, 'JSON.stringify(CHAT)')
        check('A got B\'s chat message', 'Hello from Birch at the hollow' in got and 'Birch' in got, got)

        # Host keeps the clock: B's time of day should follow A's.
        time.sleep(2)
        ta, tb = E(A, 'st.t'), E(B, 'st.t')
        check('time of day follows the host', abs(ta - tb) < 0.02, f'A {ta:.4f} B {tb:.4f}')

        # Leave cleanly.
        E(B, 'NETKIT.leave()'); time.sleep(1.5)
        check('A notices B left', E(A, 'NETKIT.players().length') == 1 and E(A, 'NET.others.size') == 0)

        A.bring_to_front(); A.screenshot(path='/tmp/online_A.png')
        for tag in errs:
            if errs[tag]: print(f'page errors on {tag}:', errs[tag][:5])
        br.close()
    srv.shutdown()
    bad = [r for r in results if not r[1]]
    print(f'\n{len(results)-len(bad)}/{len(results)} checks passed')
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
