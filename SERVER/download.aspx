<%@ Page Language="C#" %>
<%@ Import Namespace="System.IO" %>
<%@ Import Namespace="System.Web.Script.Serialization" %>
<script runat="server">
    protected void Page_Load(object sender, EventArgs e)
    {
        string folder = Request.QueryString["folder"];
        string file = Request.QueryString["file"];
        string updateParam = Request.QueryString["update"];

        if (string.IsNullOrEmpty(folder) || string.IsNullOrEmpty(file))
        {
            Response.StatusCode = 400;
            Response.Write("Missing folder or file parameter");
            return;
        }

        // folder must be exactly "releases" or "debugs"
        string[] allowedFolders = { "releases", "debugs" };
        if (Array.IndexOf(allowedFolders, folder) < 0)
        {
            Response.StatusCode = 400;
            Response.Write("Invalid folder");
            return;
        }

        // file must be a safe bare filename: no path separators or dot-paths
        char[] separators = { '/', '\\' };
        if (file.IndexOfAny(separators) >= 0 ||
            file == "." || file == ".." ||
            file.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
        {
            Response.StatusCode = 400;
            Response.Write("Invalid file");
            return;
        }

        bool isUpdate = updateParam == "true" || updateParam == "1";

        string folderPath = Server.MapPath("~/" + folder);
        string filePath = Path.Combine(folderPath, file);

        if (!File.Exists(filePath))
        {
            Response.StatusCode = 404;
            Response.Write("File not found");
            return;
        }

        string countsPath = Path.Combine(folderPath, "downloads.json");
        Dictionary<string, Dictionary<string, int>> counts = new Dictionary<string, Dictionary<string, int>>();

        Application.Lock();
        try
        {
            if (File.Exists(countsPath))
            {
                string json = File.ReadAllText(countsPath);
                Dictionary<string, object> raw = null;
                try
                {
                    raw = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(json);
                }
                catch { }
                if (raw != null)
                {
                    foreach (var kv in raw)
                    {
                        Dictionary<string, int> entry = new Dictionary<string, int>();
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
                            // Legacy flat format: {"file": count}
                            entry["download"] = Convert.ToInt32(kv.Value);
                        }
                        counts[kv.Key] = entry;
                    }
                }
            }

            Dictionary<string, int> target;
            if (!counts.ContainsKey(file))
            {
                target = new Dictionary<string, int>();
                target["download"] = 0;
                target["update"] = 0;
                counts[file] = target;
            }
            else
            {
                target = counts[file];
            }

            if (isUpdate)
                target["update"] = target["update"] + 1;
            else
                target["download"] = target["download"] + 1;

            string newJson = new JavaScriptSerializer().Serialize(counts);
            File.WriteAllText(countsPath, newJson);
        }
        finally
        {
            Application.UnLock();
        }

        string url = "https://storyweaver.zeugs.me/" + folder + "/" + Uri.EscapeDataString(file);
        Response.Redirect(url);
    }
</script>