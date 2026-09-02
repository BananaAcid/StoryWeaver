<%@ Page Language="C#" AutoEventWireup="true" %>
<%@ Import Namespace="System.IO" %>
<%@ Import Namespace="System.Text.RegularExpressions" %>
<%@ Import Namespace="System.Linq" %>
<%@ Import Namespace="System.Web.Script.Serialization" %>
<script runat="server">
    protected void Page_Load(object sender, EventArgs e)
    {
        Response.ContentType = "application/json; charset=utf-8";
        Response.Cache.SetCacheability(HttpCacheability.NoCache);

        var result = new Dictionary<string, object>();
        result["releases"] = BuildBranch("releases");
        result["debugs"]   = BuildBranch("debugs");

        var json = new JavaScriptSerializer().Serialize(result);
        Response.Write(json);
    }

    class Entry
    {
        public string version   { get; set; }
        public int    build     { get; set; }
        public string uploaded  { get; set; }
        public string url       { get; set; }
        public long   size      { get; set; }
        public int    downloads { get; set; }
        public int    updates   { get; set; }
    }

    class Branch
    {
        public Entry   latest         { get; set; }
        public Entry[] all            { get; set; }
        public int     totalDownloads { get; set; }
    }

    static readonly Regex _re = new Regex(
        @"StoryWeaver v(\d+)\.(\d+)\.(\d+)\.(\d+)\.(7z|zip|tar|gz|tar\.gz)$",
        RegexOptions.IgnoreCase
    );

    Branch BuildBranch(string dirName)
    {
        var dir = Server.MapPath("~/" + dirName);
        var entries = new List<Entry>();

        var downloads = new Dictionary<string, Dictionary<string, int>>();
        var countsPath = Path.Combine(dir, "downloads.json");
        if (File.Exists(countsPath))
        {
            try
            {
                var raw = File.ReadAllText(countsPath);
                var rawDict = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(raw);
                foreach (var kv in rawDict)
                {
                    var entry = new Dictionary<string, int>();
                    entry["download"] = 0;
                    entry["update"] = 0;
                    if (kv.Value is Dictionary<string, object>)
                    {
                        var o = (Dictionary<string, object>)kv.Value;
                        if (o.ContainsKey("download")) entry["download"] = Convert.ToInt32(o["download"]);
                        if (o.ContainsKey("update")) entry["update"] = Convert.ToInt32(o["update"]);
                    }
                    else
                    {
                        entry["download"] = Convert.ToInt32(kv.Value);
                    }
                    downloads[kv.Key] = entry;
                }
            }
            catch { }
        }

        if (Directory.Exists(dir))
        {
            foreach (var f in Directory.GetFiles(dir, "StoryWeaver v*"))
            {
                var fi = new FileInfo(f);
                var ext = fi.Extension.ToLowerInvariant();
                if (ext != ".7z" && ext != ".zip" && ext != ".tar" && ext != ".gz") continue;

                var m = _re.Match(fi.Name);
                if (!m.Success) continue;

                int major = int.Parse(m.Groups[1].Value);
                int minor = int.Parse(m.Groups[2].Value);
                int patch = int.Parse(m.Groups[3].Value);
                int build = int.Parse(m.Groups[4].Value);
                var ver   = String.Format("{0}.{1}.{2}.{3}", major, minor, patch, build);

                var encoded = Uri.EscapeDataString(fi.Name);

                int dlCount = 0;
                int updCount = 0;
                if (downloads.ContainsKey(fi.Name))
                {
                    var c = downloads[fi.Name];
                    if (c.ContainsKey("download")) dlCount = c["download"];
                    if (c.ContainsKey("update")) updCount = c["update"];
                }

                entries.Add(new Entry
                {
                    version   = ver,
                    build     = build,
                    uploaded  = fi.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    url       = String.Format("https://storyweaver.zeugs.me/download.aspx?update=true&folder={0}&file={1}", dirName, encoded),
                    size      = fi.Length,
                    downloads = dlCount,
                    updates   = updCount,
                });
            }
        }

        entries = entries.OrderByDescending(e => e.build).ToList();

        Branch branch = new Branch();
        branch.latest = entries.FirstOrDefault();
        branch.all = entries.ToArray();
        branch.totalDownloads = entries.Sum(e => e.downloads + e.updates);
        return branch;
    }
</script>