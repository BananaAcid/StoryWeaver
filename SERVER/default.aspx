<%@ Page Language="C#" AutoEventWireup="true" %>
<%@ Import Namespace="System.IO" %>
<%@ Import Namespace="System.Text.RegularExpressions" %>
<%@ Import Namespace="System.Linq" %>
<%@ Import Namespace="System.Web.Script.Serialization" %>
<script runat="server">
    protected void Page_Load(object sender, EventArgs e)
    {
        Response.ContentType = "text/html; charset=utf-8";
    }
</script>
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>StoryWeaver</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',-apple-system,sans-serif;background:#1a1a2e;color:#eee;text-align:center;padding:60px 20px;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
.github{position:absolute;top:16px;right:20px;color:#888;font-size:.85rem;text-decoration:none;transition:color .15s}
.github:hover{color:#fff}
.github .lic{display:block;font-size:.72rem;color:#666}
.head{display:flex;align-items:center;justify-content:center;gap:14px;margin-bottom:12px}
.logo{height:2.2rem;width:auto;border-radius:8px;object-fit:contain;box-shadow:0 4px 12px rgba(0,0,0,.3)}
h1{font-size:2.2rem;margin:0;font-weight:300;letter-spacing:1px}
.sub{color:#888;font-size:.95rem;max-width:520px;margin-bottom:20px;line-height:1.5}
.install{color:#bbb;font-size:.85rem;max-width:560px;margin:32px auto 0;padding:16px 20px 18px;line-height:1.6;text-align:left;background:#232341;border:1px solid #33335a;border-radius:14px}
.install .cap{display:block;font-size:.78rem;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:#7b7bd6;margin-bottom:8px}
.install a{color:#4fc3f7;text-decoration:none}
.install a:hover{text-decoration:underline}
.cards{display:flex;gap:20px;flex-wrap:wrap;justify-content:center;margin:40px 0}
.card{display:flex;flex-direction:column;align-items:center;justify-content:center;width:200px;padding:28px 20px;background:#232341;border-radius:14px;text-decoration:none;color:#eee;transition:transform .15s,box-shadow .15s}
.card:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.4)}
.card .t{font-size:1.1rem;font-weight:600;margin-bottom:6px}
.card .d{font-size:.78rem;color:#888}
.dl-upd{background:#4fc3f7}
.dl-rel{background:#4fc3f7}
.dl-deb{background:#ff6b6b}
.dl-edt{background:#7bd88f}
.dl-upd .t,.dl-upd .d,.dl-rel .t,.dl-rel .d,.dl-edt .t,.dl-edt .d{color:#1a1a2e}
.dl-deb .t,.dl-deb .d{color:#fff}
.updates{display:inline-block;margin-top:28px;color:#4fc3f7;font-size:.9rem;text-decoration:none}
.updates:hover{text-decoration:underline}
</style>
</head>
<body>
<a class="github" href="https://github.com/BananaAcid/StoryWeaver">github.com/BananaAcid/StoryWeaver<span class="lic">open source &middot; MIT licensed</span></a>
<div class="head">
    <img class="logo" src="res/StoryWeaver.png" alt="StoryWeaver" onerror="this.style.display='none'"/>
    <h1>StoryWeaver</h1>
</div>
<p class="sub">AI-powered interactive storybook player. Reads aloud, illustrates the plot, and lets you choose where the adventure goes next.</p>

<div class="cards">
    <a class="card dl-rel" href="/releases/">
        <span class="t">Releases &#8595;</span>
        <span class="d">Latest stable build</span>
    </a>
    <a class="card dl-deb" href="/debugs/">
        <span class="t">Debugs &#8595;</span>
        <span class="d">Latest debug build</span>
    </a>
    <a class="card dl-edt" href="/config">
        <span class="t">Edit &#9998;</span>
        <span class="d">Edit your device configs</span>
    </a>
</div>
<p class="install"><span class="cap">Installation</span>Download a build below and extract it on your SD card under <b>/Roms/APPS/</b> (or via SFTP to <b>/mnt/mmc/Roms/APPS/</b>) so that <b>StoryWeaver.sh</b> sits directly inside <b>/Roms/APPS/</b> &mdash; no extra subfolder. On any other Linux device, just put it where you want. For detailed installation and usage instructions, see the <a href="https://github.com/BananaAcid/StoryWeaver/blob/main/README.md">README</a>.</p>
<a class="updates" href="/updates">Updates feed (JSON) &#8594;</a>
</body>
</html>