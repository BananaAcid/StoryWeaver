<%@ Page Language="C#" AutoEventWireup="true" %>
<script runat="server">
protected void Page_Load(object sender, EventArgs e)
{
    Response.ContentType = "text/plain";
    Response.Write("test.aspx works");
}
</script>
