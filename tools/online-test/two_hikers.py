"""Headless online-play test for Paperland Trails, on Ember Hollow (#hollow) only.

Player A is the dev and hosts a game on Ember Hollow. Player B is a regular player who
opens A's invite link. Both pages run in one Chrome and talk through NETKIT's same-browser
transport (BroadcastChannel), so no internet or matchmaking server is needed.

Checks: the invite carries the map, dev tools are locked for B, joining, B's camp is packed
and shown as carried, B pitches a camp that A sees, walking, chat both ways, the host's
weather, animals and clock on B, and leaving.

Usage:  python3 tools/online-test/two_hikers.py [three.min.js] [GLTFLoader.js]
The shipped index.html is never changed: the test-only hooks are injected into the copy
served to the browser (window.__E, and a switch to the same-browser connection).
"""
import http.server, json, os, re, socketserver, sys, threading, time
from playwright.sync_api import sync_playwright

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
THREE = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/threejs/build/three.min.js'
GLTF = sys.argv[2] if len(sys.argv) > 2 else '/home/claude/threejs/examples/js/loaders/GLTFLoader.js'
PORT = 8765
BASE = f'http://localhost:{PORT}/index.html'
HOOK_AT = 'hud();requestAnimationFrame(frame);'
WALK_S = float(os.environ.get('WALK_S', '8'))  # software rendering runs the game ~10x slow; hold W long enough

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
    hook = ('window.__E=s=>eval(s);'
            'if(window.__TEST_LOCAL)netConn=function(){NETKIT.config({transport:NETKIT_TRANSPORTS.local(),rate:12,joinWait:12000});return "pn";};')
    dev_hash = re.search(r"const DEV_HASH='([0-9a-f]{64})'", src).group(1)
    return src[:i] + hook + src[i:], dev_hash

results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail else ''), flush=True)
    return ok

def main():
    srv = serve()
    html, dev_hash = patched_html()
    three, gltf = open(THREE, 'rb').read(), open(GLTF, 'rb').read()
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True,
                                args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle',
                                      '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
                                      '--disable-backgrounding-occluded-windows'])
        ctx = br.new_context(viewport={'width': 360, 'height': 225})

        def route(r):
            u = r.request.url
            if u.startswith(BASE):
                return r.fulfill(status=200, content_type='text/html; charset=utf-8', body=html)
            if 'three.min.js' in u and 'localhost' not in u:
                return r.fulfill(status=200, content_type='application/javascript', body=three)
            if 'GLTFLoader' in u and 'localhost' not in u:
                return r.fulfill(status=200, content_type='application/javascript', body=gltf)
            if 'localhost' in u or u.startswith('data:') or u.startswith('blob:'):
                return r.continue_()
            return r.abort()          # the rest of the internet: blocked, keeps the test offline
        ctx.route('**/*', route)

        errs = {}
        def open_player(tag, url, dev):
            p = ctx.new_page(); errs[tag] = []
            p.on('pageerror', lambda e: errs[tag].append(str(e)[:200]))
            # both pages share storage, so each page gets its own answer for the dev key
            p.add_init_script(f"""window.__TEST_LOCAL=1;{{const g=Storage.prototype.getItem;
              Storage.prototype.getItem=function(k){{if(k==='plw-dev')return {json.dumps(dev_hash) if dev else 'null'};return g.call(this,k);}};}}""")
            p.goto(url, wait_until='load', timeout=120000)
            p.wait_for_function('typeof window.__E==="function"', timeout=120000)
            p.evaluate("()=>{const i=document.getElementById('rwIntro');if(i)i.remove();const b=document.getElementById('startBtn');if(b)b.click();}")
            return p
        E = lambda p, js: p.evaluate('s=>window.__E(s)', js)
        J = lambda p, js: json.loads(E(p, 'JSON.stringify(' + js + ')'))
        shown = lambda p, sel: p.evaluate(f"()=>{{const e=document.querySelector({json.dumps(sel)});return !!e&&getComputedStyle(e).display!=='none';}}")

        def on_hollow(tag, p):
            info = J(p, '{MAPKEY,WORLD,DEV}')
            if not check(f'{tag} is on Ember Hollow (small map)', info['MAPKEY'] == 'hollow' and info['WORLD'] is False, json.dumps(info)):
                raise SystemExit('Wrong map loaded; stopping before anything runs on the full world.')
            return info

        # ---- A: the dev, hosting on Ember Hollow
        t0 = time.time()
        A = open_player('A', BASE + '#hollow', dev=True)
        on_hollow('A', A)
        check('A has dev tools (Time, Light, Weather, map picker)', all(shown(A, s) for s in ['#timeBtn', '#lightBtn', '#weatherBtn', '.maps']))
        E(A, "NET.name='Alder';$('onName').value='Alder';"); A.evaluate("()=>window.__E(\"$('onHost').click()\")")
        A.wait_for_function('()=>window.__E("NETKIT.inSession()")', timeout=10000)
        A.evaluate("()=>window.__E(\"$('onCopy').click()\")"); time.sleep(0.5)
        msg = E(A, "$('onMsg').textContent")
        m = re.search(r'(http\S+)', msg)
        link = m.group(1) if m else ''
        check('invite link carries the map', '#hollow.pn-' in link, link)

        # ---- B: a regular player opening the invite
        B = open_player('B', link or BASE + '#hollow', dev=False)
        print(f'loaded both pages in {time.time()-t0:.1f}s', flush=True)
        info = on_hollow('B', B)
        check('B has no dev tools (no Time, Light, Weather, maps, Weather dock tab)',
              not info['DEV'] and not any(shown(B, s) for s in ['#timeBtn', '#lightBtn', '#weatherBtn', '.maps', '#dock [data-k="wp"]']))
        check('B still has the lighter-graphics option', shown(B, '#liteBtn'))
        E(B, "{const t0=toast;toast=(m,d)=>{(window.__toasts=window.__toasts||[]).push(m);t0(m,d);};}")
        E(B, "$('onName').value='Birch';$('onName').dispatchEvent(new Event('change'))")
        time.sleep(1.2)  # the invite opens the Online tab after 0.8 s
        B.evaluate("()=>window.__E(\"$('onJoin').click()\")")
        B.wait_for_function('()=>window.__E("NETKIT.inSession()&&NETKIT.players().length===2")', timeout=30000)
        check('B joined; both see 2 players, A is host',
              J(B, 'NETKIT.players().map(p=>[p.name,p.isHost])') == [['Birch', False], ['Alder', True]] or
              sorted(J(B, 'NETKIT.players().map(p=>p.name+":"+p.isHost)')) == ['Alder:true', 'Birch:false'],
              json.dumps(J(B, 'NETKIT.players().map(p=>[p.name,p.isHost])')))
        A.wait_for_function('()=>window.__E("NETKIT.players().length")===2', timeout=10000)
        check('only the host can copy the invite', shown(A, '#onCopy') and not B.evaluate("()=>!document.getElementById('onCopy').hidden"))

        if os.environ.get('NKDEBUG'):
            for k in range(4):
                time.sleep(1.5)
                print('  dbg A world t', E(A, 'NETKIT.world().t'), 'A st.t', round(E(A,'st.t'),4), '| B world t', E(B, 'NETKIT.world().t'),
                      '| A stats', E(A, 'JSON.stringify((({presenceBytes,bytesPerSec,msgsOut})=>({presenceBytes,bytesPerSec,msgsOut}))(NETKIT.stats()))'), flush=True)
            print('  dbg A errors', errs['A'][:3], 'B errors', errs['B'][:3])
            raise SystemExit(0)
        # ---- camps
        time.sleep(2)
        check('B\'s camp was packed (it stood on the host\'s camp)', E(B, 'CAMP.state') == 'carried', E(B, 'CAMP.state'))
        lab = E(A, "[...NET.others.values()][0].lab.textContent")
        E(A, 'netView()'); lst = E(A, "$('onList').textContent")
        check('A sees that Birch is carrying a camp', 'carrying camp' in lab and 'Birch' in lst and 'carrying the camp' in lst, f'{lab} | {lst}')
        check('A draws an avatar for B', E(A, 'NET.others.size') == 1)

        # ---- B walks, then pitches a camp
        AV = '[...NET.others.values()].map(o=>({x:o.x,z:o.z}))[0]'
        b0 = J(B, '{x:player.x,z:player.z}'); a0 = J(A, AV)
        B.bring_to_front(); B.keyboard.down('KeyW'); time.sleep(WALK_S); B.keyboard.up('KeyW')
        b1 = J(B, '{x:player.x,z:player.z}')
        moved = ((b1['x']-b0['x'])**2 + (b1['z']-b0['z'])**2) ** 0.5
        check('B walked', moved > 0.2, f'{moved:.2f} m')
        time.sleep(4)
        seen = J(A, AV)
        amov = ((seen['x']-a0['x'])**2 + (seen['z']-a0['z'])**2) ** 0.5
        gap = ((seen['x']-b1['x'])**2 + (seen['z']-b1['z'])**2) ** 0.5
        check('A sees B move to the new spot', abs(amov-moved) < 0.1 and gap < 0.3, f'A saw {amov:.2f} m, gap {gap:.2f} m')
        # step a few metres away from the host's camp to open ground, then pitch (test shortcut: a short teleport)
        E(B, '(()=>{for(let r=4;r<9;r+=1)for(let k=0;k<12;k++){const a=k*0.52,x=FIRE.x===9999?player.x:0;'
             'const px=NET.hx+Math.cos(a)*r,pz=NET.hz+Math.sin(a)*r,fx=px+Math.sin(a)*3.4,fz=pz+Math.cos(a)*3.4;'
             'if(walkable(px,pz,LIM,"rim")&&!blocked(fx,fz,0.8,"rim")&&!inWater(fx,fz)){player.x=px;player.z=pz;player.rot=a;return;}}})()'
             .replace('NET.hx', '(CAMP.home.fx)').replace('NET.hz', '(CAMP.home.fz)'))
        time.sleep(1)
        E(B, 'setupCamp()'); time.sleep(3)            # placement mode: the ghost camp follows you
        E(B, 'if(CP.on&&CP.ok)confirmCampPlace();')
        bf = J(B, '{x:FIRE.x,z:FIRE.z}')
        check('B pitched a camp', E(B, 'CAMP.state') == 'set', json.dumps(bf))
        time.sleep(3)
        cam = J(A, "(o=>o.camp?{key:o.camp.key,lab:o.camp.lab.textContent,fl:o.camp.fl.visible}:null)([...NET.others.values()][0])")
        check('A sees Birch\'s camp where B pitched it', cam and cam['key'] == f"{round(bf['x'],2):g},{round(bf['z'],2):g}" and 'Birch' in cam['lab'] and cam['fl'],
              json.dumps(cam))

        # ---- chat both ways
        E(B, "dockOpen('radio')"); time.sleep(0.3)
        B.fill('#dkChatIn', 'Hello from Birch'); B.evaluate("()=>document.getElementById('dkChatF').requestSubmit()")
        E(A, "dockOpen('radio')"); time.sleep(0.3)
        A.fill('#dkChatIn', 'Hi Birch, Alder here'); A.evaluate("()=>document.getElementById('dkChatF').requestSubmit()")
        time.sleep(2)
        ca, cb = E(A, 'JSON.stringify(CHAT)'), E(B, 'JSON.stringify(CHAT)')
        check('chat reaches both players', 'Hello from Birch' in ca and 'Hi Birch, Alder here' in cb, f'A {ca} | B {cb}')

        # ---- the host's environment and animals
        E(A, "startStorm(0.35,'snow');st.snow=0.4")
        i_vis = E(A, 'animals.findIndex(a=>a.g.visible)')
        E(A, f'animals[{i_vis}].x+=2.5')     # nudge one animal on the host; the guest must follow
        time.sleep(4)
        wa, wb = J(A, '{on:W.on,kind:W.kind,p:W.p,snow:st.snow}'), J(B, '{on:W.on,kind:W.kind,p:W.p,snow:st.snow}')
        check('weather matches the host (snowstorm)', wb['on'] and wb['kind'] == 'snow' and abs(wa['p']-wb['p']) < 0.05 and abs(wa['snow']-wb['snow']) < 0.05,
              f'A {wa} | B {wb}')
        if not results[-1][1]:
            print('   B world:', E(B, 'JSON.stringify(NETKIT.world())')[:400]); print('   B W:', E(B, 'JSON.stringify(W)')[:300], 'yearDay A/B', E(A,'yearDay()'), E(B,'yearDay()'))
        pa, pb = J(A, 'animals.map(a=>[a.x,a.z,a.g.visible])'), J(B, 'animals.map(a=>[a.x,a.z,a.g.visible])')
        worst = max((((x1-x2)**2+(z1-z2)**2)**0.5 for (x1, z1, v1), (x2, z2, v2) in zip(pa, pb) if v1), default=0)
        vis_same = all(v1 == v2 for (_, _, v1), (_, _, v2) in zip(pa, pb))
        check('animals match the host', len(pa) == len(pb) and vis_same and worst < 0.4, f'{len(pa)} animals, worst gap {worst:.2f} m')
        ta, tb = E(A, 'st.t'), E(B, 'st.t')
        check('time of day follows the host', abs(ta - tb) < 0.02, f'A {ta:.4f} B {tb:.4f}')

        # ---- leave
        B.evaluate("()=>window.__E(\"$('onLeave').click()\")"); time.sleep(1.5)
        ts = J(B, 'window.__toasts||[]')
        check('B is sent back to the main map after leaving', any('main map' in t for t in ts), ts[-3:])
        B.close()     # before it starts loading the full world
        time.sleep(1)
        check('A notices B left', E(A, 'NETKIT.players().length') == 1 and E(A, 'NET.others.size') == 0)

        for tag in errs:
            if errs[tag]: print(f'page errors on {tag}:', errs[tag][:5])
        br.close()
    srv.shutdown()
    bad = [r for r in results if not r[1]]
    print(f'\n{len(results)-len(bad)}/{len(results)} checks passed')
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
