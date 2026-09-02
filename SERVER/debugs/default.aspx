<%@ Page Language="C#" %>
<%@ Import Namespace="System.IO" %>
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>StoryWeaver - Debugs</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',-apple-system,sans-serif;background:#1a1a2e;color:#eee;text-align:center;padding:60px 20px;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
h1{font-size:2rem;margin-bottom:8px;font-weight:300;letter-spacing:1px}
.sub{color:#666;font-size:.85rem;margin-bottom:32px}
.dl-link{display:inline-block;background:#ff6b6b;color:#fff;text-decoration:none;font-size:1.1rem;font-weight:600;padding:18px 48px;border-radius:10px;transition:transform .15s,box-shadow .15s}
.dl-link:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(255,107,107,.35)}
.meta{color:#888;font-size:.8rem;margin-top:14px}
.back{margin-top:40px;color:#555;font-size:.8rem}
.back a{color:#ff6b6b;text-decoration:none}
.back a:hover{text-decoration:underline}
</style>
</head>
<body>
<h1>StoryWeaver &mdash; Debugs</h1>
<p class="sub">Latest debug build</p>
<%
try {
    string dir = Server.MapPath(".");
    string[] allFiles = Directory.GetFiles(dir);
    string latest = null;
    for (int i = 0; i < allFiles.Length; i++) {
        string f = allFiles[i];
        if (f.EndsWith(".zip") || f.EndsWith(".7z")) {
            if (latest == null || string.Compare(f, latest, StringComparison.OrdinalIgnoreCase) > 0) {
                latest = f;
            }
        }
    }
    if (latest != null) {
        string name = Path.GetFileName(latest);
        FileInfo fi = new FileInfo(latest);
        string size;
        if (fi.Length >= 1048576) {
            size = (fi.Length / 1048576.0).ToString("F1") + " MB";
        } else {
            size = (fi.Length / 1024.0).ToString("F1") + " KB";
        }
        string date = fi.LastWriteTimeUtc.ToString("yyyy-MM-dd HH:mm");
%>
<a class="dl-link" href="../download.aspx?folder=debugs&file=<%= Server.UrlEncode(name) %>">Download &#8595;</a>
<div class="meta"><%= name %> &mdash; <span><%= size %></span> &mdash; <span><%= date %> UTC</span></div>
<%
    } else {
%>
<p>No debugs found.</p>
<%
    }
} catch (Exception ex) {
%>
<p style="color:#f66">Error: <%= Server.HtmlEncode(ex.Message) %></p>
<%
}
%>
<p class="back"><a href="/">&#8592; Back</a></p>
</body>
</html>
