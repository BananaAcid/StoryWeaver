<%@ Page Language="C#" AutoEventWireup="true" %>
<%@ Import Namespace="System.IO" %>
<%@ Import Namespace="System.Text" %>
<%@ Import Namespace="System.Linq" %>
<%@ Import Namespace="System.Web.Script.Serialization" %>
<script runat="server">

static readonly Random _rng = new Random();
static readonly JavaScriptSerializer _json = new JavaScriptSerializer();

string EditsDir { get { return Server.MapPath("~/edits"); } }

// ── Entry point ──────────────────────────────────────────
protected void Page_Load(object sender, EventArgs e)
{
    var method = Request.HttpMethod.ToUpperInvariant();
    var id     = SanitizeId(Request.QueryString["id"] ?? "");

    // POST /c/X&finalize=1
    if (method == "POST" && id != "" && Request.QueryString["finalize"] == "1")
        { FinalizeEdit(id); return; }

    // POST /c/X&cancel=1
    if (method == "POST" && id != "" && Request.QueryString["cancel"] == "1")
        { CancelEdit(id); return; }

    // POST /c/X&save=filename
    if (method == "POST" && id != "" && Request.QueryString["save"] != null)
        { SaveFile(id, Request.QueryString["save"]); return; }

    // POST /c/X&add_profile=1
    if (method == "POST" && id != "" && Request.QueryString["add_profile"] == "1")
        { AddProfile(id); return; }

    // POST /c/X&delete_profile=filename
    if (method == "POST" && id != "" && Request.QueryString["delete_profile"] != null)
        { DeleteProfile(id, Request.QueryString["delete_profile"]); return; }

    // POST /c/X&delete_screenshot=filename
    if (method == "POST" && id != "" && Request.QueryString["delete_screenshot"] != null)
        { DeleteScreenshot(id, Request.QueryString["delete_screenshot"]); return; }

    // POST /config (upload)
    if (method == "POST" && id == "")
        { HandleUpload(); return; }

    // DELETE /c/X
    if (method == "DELETE" && id != "")
        { CancelEdit(id); return; }

    // GET /c/X&log=1
    if (method == "GET" && id != "" && Request.QueryString["log"] == "1")
        { ReturnLog(id); return; }

    // GET /c/X&download=1
    if (method == "GET" && id != "" && Request.QueryString["download"] == "1")
        { HandleDownload(id); return; }

    // GET /c/X (browser → editor, app → status)
    if (method == "GET" && id != "")
    {
        if (IsBrowserRequest())
            { RenderEditor(id); return; }
        else
            { ReturnStatus(id); return; }
    }

    // GET /config (no id → info page)
    if (method == "GET" && id == "")
        { RenderInfoPage(); return; }

    Response.StatusCode = 405;
    Response.Write("{\"error\":\"Method not allowed\"}");
}

// ── Helpers ──────────────────────────────────────────────
bool IsBrowserRequest()
{
    var ua = Request.UserAgent ?? "";
    // simple heuristic: browsers send text/html
    var accept = Request.Headers["Accept"] ?? "";
    return accept.Contains("text/html") || ua.Contains("Mozilla") || ua.Contains("Chrome") || ua.Contains("Safari");
}

string MakeId()
{
    const string chars = "abcdefghjkmnpqrstuvwxyz23456789";
    var sb = new StringBuilder(6);
    for (int i = 0; i < 6; i++) sb.Append(chars[_rng.Next(chars.Length)]);
    return sb.ToString();
}

string ReadFileText(string path)
{
    try { return File.ReadAllText(path, Encoding.UTF8); } catch { return null; }
}

void WriteFileText(string path, string content)
{
    Directory.CreateDirectory(Path.GetDirectoryName(path));
    File.WriteAllText(path, content, Encoding.UTF8);
}

string GetStatus(string id)
{
    var sp = Path.Combine(EditsDir, id, "_status.txt");
    return ReadFileText(sp) ?? "cancelled";
}

void SetStatus(string id, string status)
{
    var dir = Path.Combine(EditsDir, id);
    Directory.CreateDirectory(dir);
    WriteFileText(Path.Combine(dir, "_status.txt"), status);
}

void JsonOut(object obj)
{
    Response.ContentType = "application/json; charset=utf-8";
    Response.Write(_json.Serialize(obj));
}

// ── Upload ───────────────────────────────────────────────
void HandleUpload()
{
    string id;

    // Check for existing ID from POST form or query string
    var existingId = SanitizeId(Request.Form["id"] ?? Request.QueryString["id"] ?? "");
    if (!string.IsNullOrEmpty(existingId))
    {
        id = existingId;
    }
    else
    {
        lock (_rng) { id = MakeId(); }
    }
    var dir = Path.Combine(EditsDir, id);
    Directory.CreateDirectory(dir);

    // Clear any leftover markers from previous session
    foreach (var marker in Directory.GetFiles(dir, "_*.txt"))
    {
        try { File.Delete(marker); } catch { }
    }

    // Only process files if there are any uploaded
    bool hasFiles = false;

    // Handle multipart form upload
    if (Request.Files.Count > 0)
    {
        hasFiles = true;
        var screenshotSet = new HashSet<string>();
        var screenshotsParam = Request.Form["screenshots"];
        if (!string.IsNullOrEmpty(screenshotsParam))
            foreach (var s in screenshotsParam.Split('|'))
                screenshotSet.Add(s.Trim());
        for (int i = 0; i < Request.Files.Count; i++)
        {
            var file = Request.Files[i];
            var fileName = SanitizeFileName(file.FileName);
            if (string.IsNullOrEmpty(fileName)) continue;
            var sub = screenshotSet.Contains(fileName) ? "screenshots" : "";
            var dest = sub == "" ? Path.Combine(dir, fileName) : Path.Combine(dir, sub, fileName);
            Directory.CreateDirectory(Path.GetDirectoryName(dest));
            file.SaveAs(dest);
        }
    }
    // Handle JSON body with base64-encoded files
    else if (Request.ContentType != null && Request.ContentType.Contains("application/json"))
    {
        hasFiles = true;
        string body;
        using (var r = new StreamReader(Request.InputStream, Encoding.UTF8))
            body = r.ReadToEnd();
        var data = _json.Deserialize<Dictionary<string, object>>(body);
        var screenshotSet = new HashSet<string>();
        object ssRaw;
        if (data.TryGetValue("screenshots", out ssRaw))
        {
            var ssStr = ssRaw as string;
            if (!string.IsNullOrEmpty(ssStr))
                foreach (var s in ssStr.Split('|'))
                    screenshotSet.Add(s.Trim());
        }
        foreach (var kv in data)
        {
            if (kv.Key == "id" || kv.Key == "screenshots") continue;
            var fileName = SanitizeFileName(kv.Key);
            if (string.IsNullOrEmpty(fileName)) continue;
            var raw = kv.Value as string;
            if (raw == null) continue;
            try
            {
                var bytes = Convert.FromBase64String(raw);
                var sub = screenshotSet.Contains(fileName) ? "screenshots" : "";
                var dest = sub == "" ? Path.Combine(dir, fileName) : Path.Combine(dir, sub, fileName);
                Directory.CreateDirectory(Path.GetDirectoryName(dest));
                File.WriteAllBytes(dest, bytes);
            }
            catch { }
        }
    }
    // Handle URL-encoded form with "data" key (fallback)
    else if (!string.IsNullOrEmpty(Request.Form["data"]))
    {
        hasFiles = true;
        var body = Request.Form["data"];
        var data = _json.Deserialize<Dictionary<string, object>>(body);
        var screenshotSet = new HashSet<string>();
        object ssRaw;
        if (data.TryGetValue("screenshots", out ssRaw))
        {
            var ssStr = ssRaw as string;
            if (!string.IsNullOrEmpty(ssStr))
                foreach (var s in ssStr.Split('|'))
                    screenshotSet.Add(s.Trim());
        }
        foreach (var kv in data)
        {
            if (kv.Key == "id" || kv.Key == "screenshots") continue;
            var fileName = SanitizeFileName(kv.Key);
            if (string.IsNullOrEmpty(fileName)) continue;
            var raw = kv.Value as string;
            if (raw == null) continue;
            try
            {
                var bytes = Convert.FromBase64String(raw);
                var sub = screenshotSet.Contains(fileName) ? "screenshots" : "";
                var dest = sub == "" ? Path.Combine(dir, fileName) : Path.Combine(dir, sub, fileName);
                Directory.CreateDirectory(Path.GetDirectoryName(dest));
                File.WriteAllBytes(dest, bytes);
            }
            catch { }
        }
    }

    SetStatus(id, "editing");

    var resp = new Dictionary<string, object>();
    resp["id"] = id;
    resp["url"] = "https://sw.zeugs.me/c/" + id;
    JsonOut(resp);
}

string SanitizeId(string id)
{
    const string allowed = "abcdefghjkmnpqrstuvwxyz23456789";
    var clean = new StringBuilder(id.Length);
    foreach (var c in id)
        if (allowed.IndexOf(char.ToLowerInvariant(c)) >= 0)
            clean.Append(c);
    return clean.ToString();
}

string SanitizeFileName(string name)
{
    // Strip any path separators — only allow a plain filename
    name = Path.GetFileName(name.Replace("\\", "/")) ?? "";
    var clean = new StringBuilder(name.Length);
    foreach (var c in name)
        if (char.IsLetterOrDigit(c) || c == '.' || c == '_' || c == '-')
            clean.Append(c);
    var result = clean.ToString().TrimStart('.');
    if (!result.EndsWith(".txt", StringComparison.OrdinalIgnoreCase) &&
        !result.EndsWith(".json", StringComparison.OrdinalIgnoreCase) &&
        !result.EndsWith(".json.default", StringComparison.OrdinalIgnoreCase) &&
        !result.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase) &&
        !result.EndsWith(".jpeg", StringComparison.OrdinalIgnoreCase) &&
        !result.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
        return "";
    return result;
}

// ── Status ───────────────────────────────────────────────
void ReturnStatus(string id)
{
    var status = GetStatus(id);
    var result = new Dictionary<string, object> { { "status", status } };
    if (status == "done" && File.Exists(Path.Combine(EditsDir, id, "_preserved.txt")))
        result["preserved"] = true;
    JsonOut(result);
}

// ── Save edited file ─────────────────────────────────────
void SaveFile(string id, string filename)
{
    var dir = Path.Combine(EditsDir, id);
    if (!Directory.Exists(dir)) { Response.StatusCode = 404; JsonOut(new { error = "Session not found" }); return; }

    string content;
    using (var r = new StreamReader(Request.InputStream, Encoding.UTF8))
        content = r.ReadToEnd();

    filename = SanitizeFileName(filename);
    var dest = Path.Combine(dir, filename);
    Directory.CreateDirectory(Path.GetDirectoryName(dest));
    WriteFileText(dest, content);

    JsonOut(new { ok = true });
}

// ── Add profile ──────────────────────────────────────────
void AddProfile(string id)
{
    var dir = Path.Combine(EditsDir, id);
    if (!Directory.Exists(dir)) { Response.StatusCode = 404; JsonOut(new { error = "Session not found" }); return; }

    var uuid = Guid.NewGuid().ToString("D").ToLowerInvariant() + ".json";
    // File is created on first Save — just return the UUID
    JsonOut(new { ok = true, filename = uuid });
}

// ── Delete profile ───────────────────────────────────────
void DeleteProfile(string id, string filename)
{
    var dir = Path.Combine(EditsDir, id);
    if (!Directory.Exists(dir)) { Response.StatusCode = 404; JsonOut(new { error = "Session not found" }); return; }

    filename = SanitizeFileName(filename);
    var path = Path.Combine(dir, filename);
    if (File.Exists(path)) File.Delete(path);

    JsonOut(new { ok = true });
}

void DeleteScreenshot(string id, string filename)
{
    var dir = Path.Combine(EditsDir, id);
    if (!Directory.Exists(dir)) { Response.StatusCode = 404; JsonOut(new { error = "Session not found" }); return; }

    filename = SanitizeFileName(filename);
    var path = Path.Combine(dir, "screenshots", filename);
    if (File.Exists(path)) File.Delete(path);

    JsonOut(new { ok = true });
}

// ── Finalize (Close and send to app) ─────────────────────
void FinalizeEdit(string id)
{
    var dir = Path.Combine(EditsDir, id);
    if (!Directory.Exists(dir)) { Response.StatusCode = 404; JsonOut(new { error = "Session not found" }); return; }
    var preserve = Request.QueryString["preserve"] == "1";
    var deleteSs = Request.QueryString["delete_screenshots"] ?? "";
    if (!string.IsNullOrEmpty(deleteSs))
    {
        try { File.WriteAllText(Path.Combine(dir, "_delete_screenshots.txt"), deleteSs); } catch { }
        if (preserve)
        {
            foreach (var s in deleteSs.Split('|'))
            {
                var sp = Path.Combine(dir, "screenshots", SanitizeFileName(s.Trim()));
                if (File.Exists(sp)) try { File.Delete(sp); } catch { }
            }
        }
    }
    SetStatus(id, "done");
    if (preserve)
    {
        try { File.WriteAllText(Path.Combine(dir, "_preserved.txt"), "1"); } catch { }
    }
    else
    {
        // Mark for cleanup after the app downloads
        try { File.WriteAllText(Path.Combine(dir, "_cleanup.txt"), "1"); } catch { }
    }
    JsonOut(new { ok = true });
}

// ── Cancel ───────────────────────────────────────────────
void CancelEdit(string id)
{
    var dir = Path.Combine(EditsDir, id);
    if (Directory.Exists(dir))
    {
        try { Directory.Delete(dir, true); } catch { }
    }
    JsonOut(new { ok = true });
}

// ── Log ──────────────────────────────────────────────────
void ReturnLog(string id)
{
    var dir = Path.Combine(EditsDir, id);
    if (!Directory.Exists(dir)) { Response.StatusCode = 404; Response.Write("Not found"); return; }
    var logContent = ReadFileText(Path.Combine(dir, "log.txt")) ?? "";
    Response.ContentType = "text/plain; charset=utf-8";
    Response.Write(logContent);
}

// ── Download ─────────────────────────────────────────────
void HandleDownload(string id)
{
    var dir = Path.Combine(EditsDir, id);
    if (!Directory.Exists(dir)) { Response.StatusCode = 404; JsonOut(new { error = "Session not found" }); return; }

    var result = new Dictionary<string, object>();
    var configJson = ReadFileText(Path.Combine(dir, "config.json"));
    var configDefault = ReadFileText(Path.Combine(dir, "config.json.default"));
    var aiJson = ReadFileText(Path.Combine(dir, "config.ai.json"));
    var aiDefault = ReadFileText(Path.Combine(dir, "config.ai.json.default"));

    if (configJson != null)
    {
        try { result["config.json"] = _json.DeserializeObject(configJson); } catch { result["config.json"] = configJson; }
    }
    if (configDefault != null)
    {
        try { result["config.json.default"] = _json.DeserializeObject(configDefault); } catch { result["config.json.default"] = configDefault; }
    }
    if (aiJson != null)
    {
        try { result["config.ai.json"] = _json.DeserializeObject(aiJson); } catch { result["config.ai.json"] = aiJson; }
    }
    if (aiDefault != null)
    {
        try { result["config.ai.json.default"] = _json.DeserializeObject(aiDefault); } catch { result["config.ai.json.default"] = aiDefault; }
    }

    // profiles
    var profiles = new Dictionary<string, object>();
    var deleteProfiles = new List<string>();
    foreach (var f in Directory.GetFiles(dir, "*.json"))
    {
        var fn = Path.GetFileName(f);
        if (fn.StartsWith("_")) continue; // skip _status.txt, etc.
        if (fn == "config.json" || fn == "config.json.default" || fn == "config.ai.json" || fn == "config.ai.json.default") continue;

        // check if it's a profile file (has profileTitle) or a delete marker
        var fc = ReadFileText(f);
        if (fc != null)
        {
            try
            {
                var obj = _json.DeserializeObject(fc);
                profiles[fn] = obj;
            }
            catch { profiles[fn] = fc; }
        }
    }
    result["profiles"] = profiles;
    result["delete_profiles"] = deleteProfiles;

    // deleted screenshots list
    var deleteSsPath = Path.Combine(dir, "_delete_screenshots.txt");
    if (File.Exists(deleteSsPath))
    {
        var raw = ReadFileText(deleteSsPath) ?? "";
        result["delete_screenshots"] = raw.Split('|').Select(s => s.Trim()).Where(s => s.Length > 0).ToList();
    }

    // Clean up after serving if marked for cleanup
    if (File.Exists(Path.Combine(dir, "_cleanup.txt")))
    {
        try { Directory.Delete(dir, true); } catch { }
    }

    JsonOut(result);
}

// ── Editor HTML page ─────────────────────────────────────
void RenderEditor(string id)
{
    var dir = Path.Combine(EditsDir, id);
    if (!Directory.Exists(dir)) { RenderInfoPage("Session not found or expired.", id); return; }

    var configJson = ReadFileText(Path.Combine(dir, "config.json")) ?? "";
    var configDefault = ReadFileText(Path.Combine(dir, "config.json.default")) ?? "";
    var aiJson = ReadFileText(Path.Combine(dir, "config.ai.json")) ?? "";
    var aiDefault = ReadFileText(Path.Combine(dir, "config.ai.json.default")) ?? "";
    var logContent = ReadFileText(Path.Combine(dir, "log.txt")) ?? "";

    var profilesHtml = new StringBuilder();
    foreach (var f in Directory.GetFiles(dir, "*.json").OrderBy(p => p))
    {
        var fn = Path.GetFileName(f);
        if (fn.StartsWith("_")) continue;
        if (fn == "config.json" || fn == "config.json.default" || fn == "config.ai.json" || fn == "config.ai.json.default") continue;

        var fc = ReadFileText(f) ?? "{}";
        var title = fn;
        try
        {
            var obj = _json.Deserialize<Dictionary<string, object>>(fc);
            if (obj != null && obj.ContainsKey("profileTitle"))
                title = obj["profileTitle"] as string ?? fn;
        }
        catch { }

        profilesHtml.AppendFormat(@"
<details id=""prof_{1}"">
  <summary>{0}</summary>
  <textarea id=""file_{1}"" class=""code"" rows=""12"" spellcheck=""false"" data-original=""{2}"" oninput=""markUnsaved('{1}')"">{2}</textarea>
  <div class=""btn-row"">
    <button onclick=""saveFile('{1}')"">Save</button>
    <button class=""danger"" onclick=""deleteProfile('{1}')"">Delete Profile</button>
  </div>
</details>",
            Ht(title), Ht(fn), Ht(fc));
    }

    var screenshotsDir = Path.Combine(dir, "screenshots");
    var screenshotsHtml = new StringBuilder();
    if (Directory.Exists(screenshotsDir))
    {
        var ssFiles = Directory.GetFiles(screenshotsDir, "*.png").OrderByDescending(f => f).ToList();
        if (ssFiles.Count > 0)
        {
            screenshotsHtml.Append("<div class=\"ss-grid\">");
            foreach (var ss in ssFiles)
            {
                var ssName = Path.GetFileName(ss);
                var ssUrl = "https://storyweaver.zeugs.me/edits/" + Ht(id) + "/screenshots/" + Uri.EscapeDataString(ssName);
                screenshotsHtml.AppendFormat("<div class=\"ss-item\"><a href=\"{0}\" target=\"_blank\" class=\"ss-thumb\"><img src=\"{0}\" alt=\"\"></a><button class=\"danger ss-del\" data-name=\"{1}\" onclick=\"deleteScreenshot(this.dataset.name)\">Delete</button></div>", ssUrl, Ht(ssName));
            }
            screenshotsHtml.Append("</div>");
        }
    }

    var jsSid = Ht(id);
    var jsCode = "<script>\n"
        + "var SID = '" + jsSid + "';\n"
        + "var _cancelOverlay = null;\n"
        + "var _lastRawLog = '';\n"
        + "\n"
        + "function colorizeLog(rawText) {\n"
        + "  var pre = document.getElementById('logContent');\n"
        + "  if (!pre) return;\n"
        + "  var lines = rawText.split('\\n');\n"
        + "  if (lines.length > 200) lines = lines.slice(-200);\n"
        + "  var apiOnly = document.getElementById('logApiOnlyCheck');\n"
        + "  if (apiOnly && apiOnly.checked) lines = lines.filter(function(l){ return l.indexOf('[API') === 0; });\n"
        + "  var html = lines.map(function(line) {\n"
        + "    var colored = line.replace(/^(\\[[^\\]]*\\])/, '<span class=\"ts\">$1</span>');\n"
        + "    colored = colored.replace(/\\[API DEBUG\\]/g, '<span class=\"ts ts-api-debug\">[API DEBUG]</span>');\n"
        + "    colored = colored.replace(/\\[API\\]/g, '<span class=\"ts ts-api\">[API]</span>');\n"
        + "    colored = colored.replace(/(model=[^\\s,\\)\\]<>]*)/g, '<span class=\"model\">$1</span>');\n"
        + "    return '<div>' + (colored || '&nbsp;') + '</div>';\n"
        + "  }).join('');\n"
        + "  pre.innerHTML = html;\n"
        + "  var badge = document.getElementById('logBadge');\n"
        + "  if (badge) badge.textContent = '(' + lines.length + ' lines)';\n"
        + "}\n"
        + "\n"
        + "function pollLog() {\n"
        + "  fetch('/config/' + SID + '?log=1').then(function(r){ return r.text(); })\n"
        + "    .then(function(t){ if(t && t.trim()) { _lastRawLog = t; colorizeLog(t); } }).catch(function(){});\n"
        + "}\n"
        + "\n"
        + "function toggleApiFilter() {\n"
        + "  if (_lastRawLog) colorizeLog(_lastRawLog);\n"
        + "}\n"
        + "\n"
        + "function toggleLogWrap() {\n"
        + "  var pre = document.getElementById('logContent');\n"
        + "  var cb = document.getElementById('logWrapCheck');\n"
        + "  if (!pre || !cb) return;\n"
        + "  pre.style.whiteSpace = cb.checked ? 'pre-wrap' : 'pre';\n"
        + "}\n"
        + "\n"
        + "function pollStatus() {\n"
        + "  fetch('/config/' + SID, { headers: { 'Accept': 'application/json' } })\n"
        + "    .then(function(r){ return r.json(); })\n"
        + "    .then(function(d){ if(d.status === 'cancelled') showCancelOverlay(); })\n"
        + "    .catch(function(){});\n"
        + "}\n"
        + "function pollAll() { pollStatus(); pollLog(); }\n"
        + "var _pollTimer = setInterval(pollAll, 5000);\n"
        + "setTimeout(function(){ var lp = document.getElementById('logContent'); if(lp && lp.textContent.trim()) colorizeLog(lp.textContent); }, 100);\n"
        + "\n"
        + "function showCancelOverlay() {\n"
        + "  if (_cancelOverlay) return;\n"
        + "  clearInterval(_pollTimer);\n"
        + "  _cancelOverlay = document.createElement('div');\n"
        + "  _cancelOverlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:999;color:#eee;text-align:center;padding:40px';\n"
        + "  _cancelOverlay.innerHTML = '<h1 style=\"color:#f88;font-size:1.8rem;margin-bottom:16px\">App cancelled editing</h1>'\n"
        + "    + '<p style=\"color:#aaa;font-size:1rem;max-width:500px;line-height:1.6\">This session was cancelled by the app &mdash; the user pressed <strong>Cancel</strong> in the waiting dialog on the device.<br><br>All unsaved changes have been discarded and the session files have been removed.</p>'\n"
        + "    + '<button onclick=\"window.close()\" style=\"margin-top:30px;background:#4fc3f7;color:#1a1a2e;border:none;border-radius:8px;padding:14px 36px;font-size:1.1rem;font-weight:600;cursor:pointer\">Close page</button>';\n"
        + "  document.body.appendChild(_cancelOverlay);\n"
        + "}\n"
        + "\n"
        + "function markUnsaved(name) {\n"
        + "  var ta = document.getElementById('file_' + name);\n"
        + "  if (!ta) return;\n"
        + "  if (!ta.dataset.original) ta.dataset.original = ta.value;\n"
        + "  var sum = ta.closest('details').querySelector('summary');\n"
        + "  if (!sum) return;\n"
        + "  if (!sum.dataset.base) sum.dataset.base = sum.textContent.replace(' *unsaved', '');\n"
        + "  var changed = ta.value !== ta.dataset.original;\n"
        + "  sum.textContent = sum.dataset.base + (changed ? ' *unsaved' : '');\n"
        + "}\n"
        + "\n"
        + "function saveFile(name) {\n"
        + "  var ta = document.getElementById('file_' + name);\n"
        + "  if (!ta) return;\n"
        + "  var isProfile = name !== 'config.json' && name !== 'config.ai.json';\n"
        + "  if (name.match(/\\.json$/)) {\n"
        + "    var errEl = document.getElementById('error_' + name);\n"
        + "    try {\n"
        + "      var parsed = JSON.parse(ta.value);\n"
        + "      if (errEl) errEl.parentNode.removeChild(errEl);\n"
        + "      if (isProfile && !parsed.profileTitle) {\n"
        + "        var err = document.createElement('pre');\n"
        + "        err.id = 'error_' + name;\n"
        + "        err.style.cssText = 'background:#2a1a1a;color:#f88;border:1px solid #844;border-radius:4px;padding:8px;margin-top:6px;font-size:13px;overflow:auto;white-space:pre-wrap';\n"
        + "        err.textContent = 'JSON Error: Missing required key: \"profileTitle\"';\n"
        + "        ta.parentNode.appendChild(err);\n"
        + "        return;\n"
        + "      }\n"
        + "    } catch(e) {\n"
        + "      var errEl = document.getElementById('error_' + name); if (errEl) errEl.parentNode.removeChild(errEl);\n"
        + "      var err = document.createElement('pre');\n"
        + "      err.id = 'error_' + name;\n"
        + "      err.style.cssText = 'background:#2a1a1a;color:#f88;border:1px solid #844;border-radius:4px;padding:8px;margin-top:6px;font-size:13px;overflow:auto;white-space:pre-wrap';\n"
        + "      err.textContent = 'JSON Error: ' + e.message;\n"
        + "      ta.parentNode.appendChild(err);\n"
        + "      return;\n"
        + "    }\n"
        + "  }\n"
        + "  var btn = event && event.target ? event.target : null;\n"
        + "  if (btn) { btn.textContent = 'Saving...'; btn.disabled = true; }\n"
        + "  fetch('/config/' + SID + '?save=' + encodeURIComponent(name), { method:'POST', body: ta.value })\n"
        + "    .then(function(r){ return r.json(); }).then(function(d){ if(d.ok) {\n"
        + "      var el = document.getElementById('error_' + name); if (el) el.parentNode.removeChild(el);\n"
        + "      ta.dataset.original = ta.value;\n"
        + "      if (isProfile) {\n"
        + "        try {\n"
        + "          var p = JSON.parse(ta.value);\n"
        + "          if (p && p.profileTitle) {\n"
        + "            var det = ta.closest('details');\n"
        + "            if (det) {\n"
        + "              det.querySelector('summary').textContent = p.profileTitle;\n"
        + "              det.querySelector('summary').dataset.base = p.profileTitle;\n"
        + "              det.dataset.saved = 'true';\n"
        + "            }\n"
        + "          }\n"
        + "        } catch(ee) {}\n"
        + "      }\n"
        + "      var sum = ta.closest('details').querySelector('summary');\n"
        + "      if (sum) sum.dataset.base = sum.textContent.replace(' *unsaved', '');\n"
        + "      if (btn) { btn.textContent = 'Saved'; var b = btn; setTimeout(function(){ b.textContent = 'Save'; b.disabled = false; }, 1500); }\n"
        + "    } })\n"
        + "    .catch(function(){ if(btn) { btn.textContent = 'Error'; setTimeout(function(){ btn.textContent = 'Save'; btn.disabled = false; }, 2000); } })\n"
        + "}\n"
        + "\n"
        + "function resetDefaults(name) {\n"
        + "  var ta = document.getElementById('file_' + name);\n"
        + "  if (!ta) return;\n"
        + "  var defName = name.replace('.json','.json.default');\n"
        + "  fetch('/config/' + SID + '?download=' + defName)\n"
        + "    .then(function(r){ return r.text(); }).then(function(t){ if(t) { ta.value = t; ta.dataset.original = t; markUnsaved(name); } })\n"
        + "    .catch(function(){ alert('Could not load defaults'); })\n"
        + "}\n"
        + "\n"
        + "function addProfile() {\n"
        + "  fetch('/config/' + SID + '?add_profile=1', { method:'POST' })\n"
        + "    .then(function(r){ return r.json(); })\n"
        + "    .then(function(d){\n"
        + "      if (!d.ok) { alert('Failed to add profile'); return; }\n"
        + "      var fn = d.filename;\n"
        + "      var details = document.createElement('details');\n"
        + "      details.id = 'prof_' + fn;\n"
        + "      details.dataset.saved = 'false';\n"
        + "      var summary = document.createElement('summary');\n"
        + "      summary.textContent = 'My Adventure Settings';\n"
        + "      details.appendChild(summary);\n"
        + "      var ta = document.createElement('textarea');\n"
        + "      ta.id = 'file_' + fn;\n"
        + "      ta.className = 'code';\n"
        + "      ta.rows = 12;\n"
        + "      ta.spellcheck = false;\n"
        + "      ta.value = '{\\n    \\\"profileTitle\\\": \\\"My Adventure Settings\\\",\\n\\n    \\\"speech\\\": {\\n        \\\"voice\\\": \\\"alloy\\\"\\n    },\\n\\n    \\\"promptCustomStoryAddition\\\": \\\"\\\",\\n    \\\"promptCustomThemeAddition\\\": \\\"Restrictions for story themes: No Horror, No desperate situations, not creepy or bloody, no exessive violence.\\\"\\n}';\n"
        + "      ta.dataset.original = ta.value;\n"
        + "      ta.setAttribute('oninput', 'markUnsaved(\"' + fn + '\")');\n"
        + "      details.appendChild(ta);\n"
        + "      var div = document.createElement('div');\n"
        + "      div.className = 'btn-row';\n"
        + "      var saveBtn = document.createElement('button');\n"
        + "      saveBtn.textContent = 'Save';\n"
        + "      saveBtn.onclick = function() { saveFile(fn); };\n"
        + "      div.appendChild(saveBtn);\n"
        + "      var delBtn = document.createElement('button');\n"
        + "      delBtn.textContent = 'Delete Profile';\n"
        + "      delBtn.className = 'danger';\n"
        + "      delBtn.onclick = function() { deleteProfile(fn); };\n"
        + "      div.appendChild(delBtn);\n"
        + "      details.appendChild(div);\n"
        + "      var addBtn = document.querySelector('.add-profile-btn');\n"
        + "      if (addBtn) {\n"
        + "        addBtn.parentNode.insertBefore(details, addBtn);\n"
        + "      } else {\n"
        + "        document.body.appendChild(details);\n"
        + "      }\n"
        + "    })\n"
        + "    .catch(function(){ alert('Failed to add profile'); })\n"
        + "}\n"
        + "\n"
        + "function deleteProfile(name) {\n"
        + "  var ta = document.getElementById('file_' + name);\n"
        + "  if (!ta) return;\n"
        + "  var details = ta.closest('details');\n"
        + "  if (!details) return;\n"
        + "  if (details.dataset.saved === 'false') {\n"
        + "    details.parentNode.removeChild(details);\n"
        + "    return;\n"
        + "  }\n"
        + "  if (!confirm('Delete this profile?')) return;\n"
        + "  fetch('/config/' + SID + '?delete_profile=' + encodeURIComponent(name), { method:'POST' })\n"
        + "    .then(function(r){ return r.json(); }).then(function(d){ if (d.ok) { details.parentNode.removeChild(details); } })\n"
        + "    .catch(function(){ alert('Failed to delete profile'); })\n"
        + "}\n"
        + "\n"
        + "function deleteScreenshot(name) {\n"
        + "  var items = document.querySelectorAll('.ss-item');\n"
        + "  var target = null;\n"
        + "  for (var i = 0; i < items.length; i++) {\n"
        + "    var btn = items[i].querySelector('.ss-del');\n"
        + "    if (btn && btn.getAttribute('data-name') === name) { target = items[i]; break; }\n"
        + "  }\n"
        + "  if (!target) return;\n"
        + "  var img = target.querySelector('.ss-thumb img');\n"
        + "  var btn = target.querySelector('.ss-del');\n"
        + "  if (target.classList.contains('ss-deleted')) {\n"
        + "    target.classList.remove('ss-deleted');\n"
        + "    btn.textContent = 'Delete';\n"
        + "  } else {\n"
        + "    target.classList.add('ss-deleted');\n"
        + "    btn.textContent = 'Keep';\n"
        + "  }\n"
        + "}\n"
        + "\n"
        + "function finalize() {\n"
        + "  if(!confirm('Send all changes to the app?')) return;\n"
        + "  var preserve = document.getElementById('preserveCheck').checked ? '&preserve=1' : '';\n"
        + "  var deleted = [];\n"
        + "  var items = document.querySelectorAll('.ss-item.ss-deleted');\n"
        + "  for (var i = 0; i < items.length; i++) {\n"
        + "    var btn = items[i].querySelector('.ss-del');\n"
        + "    if (btn) deleted.push(btn.getAttribute('data-name'));\n"
        + "  }\n"
        + "  var ssParam = deleted.length > 0 ? '&delete_screenshots=' + encodeURIComponent(deleted.join('|')) : '';\n"
        + "  fetch('/config/' + SID + '?finalize=1' + preserve + ssParam, { method:'POST' })\n"
        + "    .then(function(r){ return r.json(); }).then(function(d){ if(d.ok) { document.body.innerHTML='<div style=\"text-align:center;padding:80px 20px;color:#7ac\"><h1>Changes sent!</h1><p style=\"color:#888\">The app will download the changes shortly.</p><button onclick=\"location.href=\\'/config\\'\" style=\"margin-top:30px;background:#4fc3f7;color:#1a1a2e;border:none;border-radius:8px;padding:14px 36px;font-size:1.1rem;font-weight:600;cursor:pointer\">Back to start</button></div>' } })\n"
        + "    .catch(function(){ alert('Failed to finalize'); })\n"
        + "}\n"
        + "\n"
        + "function cancelEdit() {\n"
        + "  if(!confirm('Cancel editing and discard all changes?')) return;\n"
        + "  fetch('/config/' + SID + '?cancel=1', { method:'POST' })\n"
        + "    .then(function(r){ return r.json(); }).then(function(d){ if(d.ok) { document.body.innerHTML='<div style=\"text-align:center;padding:80px 20px;color:#f88\"><h1>Cancelled</h1><p style=\"color:#888\">No changes were sent to the app.</p></div>' } })\n"
        + "    .catch(function(){ alert('Failed to cancel'); })\n"
        + "}\n"
        + "</" + "script>\n";
    var html = @"<!DOCTYPE html>
<html lang=""en"">
<head>
<meta charset=""UTF-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Story Weaver &mdash; Config Editor</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#111;color:#ddd;font-family:system-ui,-apple-system,sans-serif;padding:20px;max-width:800px;margin:0 auto}
h1{color:#7ac;font-size:1.4rem;margin-bottom:4px}
p{color:#888;font-size:0.85rem;margin-bottom:20px}
h2{color:#7ac;font-size:1rem;margin-bottom:8px}
details{background:#1a1a2e;border:1px solid #333;border-radius:8px;margin-bottom:10px;padding:10px 14px}
details[open]{border-color:#7ac}
summary{cursor:pointer;color:#7ac;font-weight:600;font-size:0.95rem;padding:2px 0;text-align:left}
textarea.code{width:100%;background:#0d0d1a;color:#ccc;border:1px solid #333;border-radius:4px;padding:8px;font-family:'Cascadia Code','Fira Code','Consolas',monospace;font-size:13px;line-height:1.5;margin-top:8px}
.btn-row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
button{background:#2a3a4a;color:#ddd;border:none;border-radius:4px;padding:6px 16px;cursor:pointer;font-size:0.85rem}
button:hover{background:#3a4a5a}
button.primary{background:#2a6a8a;color:#fff}
button.primary:hover{background:#3a7a9a}
button.danger{background:#6a2a2a;color:#f88}
button.danger:hover{background:#8a3a3a}
hr{border:none;border-top:1px solid #333;margin:20px 0}
.master-bar{background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:14px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:20px}
.notice{background:#2a2a1a;border:1px solid #665;border-radius:8px;padding:12px;margin-bottom:16px;color:#cc8;font-size:0.85rem}
.notice code{background:#222;padding:1px 5px;border-radius:3px;color:#7ac}
.profiles-hint{color:#888;font-size:0.85rem;margin-bottom:12px;line-height:1.5}
pre.log{background:#0d0d1a;color:#ccc;border:1px solid #333;border-radius:4px;padding:8px;font-family:'Cascadia Code','Fira Code','Consolas',monospace;font-size:13px;line-height:2;margin-top:8px;overflow:auto;white-space:pre;max-height:400px}
pre.log div{margin:0;padding:0;line-height:1.7}
.ts{color:#7ac}
.ts.ts-api{color:#f88}
.ts.ts-api-debug{color:#fa4}
.model{color:#5d5;font-weight:700}
.ss-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin:10px 0}
.ss-item{display:flex;flex-direction:column;gap:4px}
.ss-thumb{display:block;aspect-ratio:1;overflow:hidden;border-radius:6px;border:1px solid #333}
.ss-thumb img{width:100%;height:100%;object-fit:contain;background:#111;display:block}
.ss-del{font-size:0.75rem;padding:3px 6px}
.ss-deleted{opacity:0.5}
</style>
</head>
<body>

<h1>Story Weaver &mdash; Config Editor</h1>
<p>Session: <code>" + Ht(id) + @"</code></p>

<div class=""notice"">
  Edit the files below. Use <strong>Save</strong> per file to store changes on the server without sending to the app.
  When done, click <strong>Close and send to app</strong> below to notify the app to download the changes.
</div>

<details>
  <summary>config.json</summary>
  <textarea id=""file_config.json"" class=""code"" rows=""16"" spellcheck=""false"" data-original=""" + Ht(configJson) + @""" oninput=""markUnsaved('config.json')"">" + Ht(configJson) + @"</textarea>
  <div class=""btn-row"">
    <button onclick=""saveFile('config.json')"">Save</button>
    <button onclick=""resetDefaults('config.json')"">Reset to defaults</button>
  </div>
</details>

<details>
  <summary>config.ai.json</summary>
  <textarea id=""file_config.ai.json"" class=""code"" rows=""12"" spellcheck=""false"" data-original=""" + Ht(aiJson) + @""" oninput=""markUnsaved('config.ai.json')"">" + Ht(aiJson) + @"</textarea>
  <div class=""btn-row"">
    <button onclick=""saveFile('config.ai.json')"">Save</button>
    <button onclick=""resetDefaults('config.ai.json')"">Reset to defaults</button>
  </div>
</details>

<details>
  <summary>Event Log <span id=""logBadge"" style=""color:#888;font-weight:400;font-size:0.8rem""></span></summary>
  <div style=""margin-top:8px;font-size:0.85rem;color:#888;display:flex;align-items:center;gap:6px"">
    <input type=""checkbox"" id=""logWrapCheck"" onchange=""toggleLogWrap()""> Line break
    <input type=""checkbox"" id=""logApiOnlyCheck"" onchange=""toggleApiFilter()""> API only
  </div>
  <pre id=""logContent"" class=""log"">" + Ht(logContent) + @"</pre>
</details>

<hr>
<h2>Profiles</h2>
<p class=""profiles-hint"">Any setting from <code>config.json</code> or <code>config.ai.json</code> can be overridden per profile &mdash; profile values take precedence over the main configuration.</p>
<p class=""profiles-hint"">When a profile is active, changing a setting that already exists in that profile will only update the profile (not the main config). If the profile does not have that setting yet, the change goes to the main config instead.</p>

" + profilesHtml.ToString() + @"

<div style=""text-align:center;margin-top:10px"">
  <button class=""add-profile-btn"" onclick=""addProfile()"">+ Add new profile</button>
</div>

" + (screenshotsHtml.Length > 0 ? @"<hr>
<h2>Screenshots</h2>
<p class=""profiles-hint"">Hold MENU on the device to capture. Taken on next config upload.</p>
" + screenshotsHtml.ToString() : "") + @"

<div class=""master-bar"">
  <label style=""display:flex;align-items:center;gap:6px;font-size:0.85rem;color:#888;cursor:pointer"">
    <input type=""checkbox"" id=""preserveCheck""> Preserve ID for later
  </label>
  <button class=""primary"" onclick=""finalize()"">Close and send to app</button>
  <button class=""danger"" onclick=""cancelEdit()"">Cancel, send no changes</button>
</div>

" + jsCode + @"
</body>
</html>";

    Response.ContentType = "text/html; charset=utf-8";
    Response.Write(html);
}

string Ht(string s)
{
    return Server.HtmlEncode(s ?? "");
}

// ── Info page ────────────────────────────────────────────
void RenderInfoPage(string extraMsg = null, string code = null)
{
    var extra = "";
    if (extraMsg != null)
        extra = "<div class=\"notice\" style=\"background:#3a1a1a;border-color:#844;color:#f88\">" + Ht(extraMsg) + "</div>";

    var html = @"<!DOCTYPE html>
<html lang=""en"">
<head>
<meta charset=""UTF-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Story Weaver &mdash; Config Editor</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',-apple-system,sans-serif;background:#1a1a2e;color:#eee;text-align:center;padding:60px 20px;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
h1{font-size:2rem;margin-bottom:8px;font-weight:300;letter-spacing:1px;color:#eee}
h2{color:#7ac;font-size:1.1rem;margin-top:24px}
p,li{color:#aaa;font-size:0.9rem;line-height:1.6}
code{background:#222;padding:1px 5px;border-radius:3px;color:#7ac}
ol{padding-left:20px;text-align:left}
.notice{background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:12px;margin:16px 0;text-align:left}
.open-btn{display:inline-block;background:#4fc3f7;color:#1a1a2e;text-decoration:none;font-size:1.1rem;font-weight:600;padding:16px 32px;border-radius:10px;border:none;cursor:pointer;transition:transform .15s,box-shadow .15s}
.open-btn:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(79,195,247,.35)}
</style>
</head>
<body>

<h1>Story Weaver &mdash; Config Editor</h1>
<p>Edit your Story Weaver configuration and profiles online.</p>

<div class=""notice"">
  <strong>How it works:</strong>
  <ol>
    <li>In the Story Weaver app, open the menu and select <strong>Edit Config Online</strong>.</li>
    <li>The app uploads your current config and profiles, then shows you a short code.</li>
    <li>Open this page with that code to edit: <strong>sw.zeugs.me/c/CODE</strong> in your browser, or just enter it below.</li>
    <li>Edit config files and profiles, then click <strong>Close and send to app</strong>.</li>
    <li>The app downloads the changes and reloads automatically.</li>
  </ol>
</div>

" + extra + @"

<h2>Enter session code</h2>
<p>Start from the Story Weaver app to create a new session. The app will give you a 6-character code to use here.</p>
<div style=""display:flex;gap:8px;margin-top:16px;max-width:400px;width:100%"">
  <input id=""codeInput"" type=""text"" maxlength=""6"" placeholder=""Enter code"" style=""flex:1;background:#0d0d1a;color:#ddd;border:1px solid #333;border-radius:10px;padding:8px 12px;font-size:1rem;text-transform:lowercase;text-align:center;outline:none"" autofocus onkeydown=""if(event.key==='Enter')openCode()"">
  <button class=""open-btn"" onclick=""openCode()"">Open</button>
</div>
<span id=""initCode"" style=""display:none"">" + (code != null ? Ht(code) : "") + @"</span>
<script>
document.addEventListener('DOMContentLoaded',function(){
  var inp = document.getElementById('codeInput');
  if (inp) inp.focus();
  var INIT_CODE = document.getElementById('initCode').textContent;
  if (INIT_CODE) {
    inp.value = INIT_CODE;
    inp.select();
    inp.focus();
  }
});
function openCode() {
  var code = document.getElementById('codeInput').value.trim().toLowerCase();
  if(code) location.href = '/config/' + encodeURIComponent(code);
}
" + "</" + "script>" + @"
</body>
</html>";

    Response.ContentType = "text/html; charset=utf-8";
    Response.Write(html);
}
</script>
