using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;

static class LayoutFeatures {
    public static object Apply(WordprocessingDocument document, string? targetId, JsonElement props) {
        var operation = props.GetProperty("operation").GetString();
        if (operation == "theme") {
            var theme = document.MainDocumentPart!.ThemePart?.Theme ?? throw new InvalidOperationException("THEME_MISSING");
            foreach (var entry in props.GetProperty("properties").EnumerateObject()) {
                var tokens = entry.Name.Split('.');
                OpenXmlElement? node = tokens[1] switch {
                    "name" => theme,
                    "fontScheme" => theme.Descendants().FirstOrDefault(e => e.LocalName == "fontScheme"),
                    "colorScheme" => theme.Descendants().FirstOrDefault(e => e.LocalName == "clrScheme"),
                    "font" => theme.Descendants().FirstOrDefault(e => e.LocalName == tokens[2] + "Font")?.ChildElements.FirstOrDefault(e => e.LocalName == (tokens[3] == "eastAsia" ? "ea" : tokens[3])),
                    _ => throw new ArgumentException("THEME_PROPERTY_UNSUPPORTED") };
                if (node == null) throw new InvalidOperationException("THEME_NODE_MISSING");
                node.SetAttribute(new OpenXmlAttribute("", tokens[1] == "font" ? "typeface" : "name", "", entry.Value.GetString()!));
            }
            theme.Save(); return new { operation, applied = true };
        }
        if (operation == "frame") {
            var roots = new List<OpenXmlElement> { document.MainDocumentPart!.Document };
            roots.AddRange(document.MainDocumentPart.HeaderParts.Select(p => (OpenXmlElement)p.Header));
            roots.AddRange(document.MainDocumentPart.FooterParts.Select(p => (OpenXmlElement)p.Footer));
            var target = roots.SelectMany(r => r.Descendants<Paragraph>()).Single(p => p.GetAttribute("id", "urn:word-module-studio:objects:v1").Value == targetId);
            var ppr = target.ParagraphProperties ??= new ParagraphProperties();
            var frame = new FrameProperties();
            foreach (var entry in props.GetProperty("attributes").EnumerateObject())
                frame.SetAttribute(new OpenXmlAttribute("w", entry.Name, "http://schemas.openxmlformats.org/wordprocessingml/2006/main", entry.Value.ToString()));
            var old = ppr.GetFirstChild<FrameProperties>();
            if (old != null) ppr.ReplaceChild(frame, old); else ppr.AddChild(frame, true);
            foreach (var root in roots.OfType<OpenXmlPartRootElement>()) root.Save();
            return new { operation, applied = true };
        }
        if (operation == "embed_fonts") {
            var main = document.MainDocumentPart!;
            var tablePart = main.FontTablePart ?? main.AddNewPart<FontTablePart>();
            tablePart.Fonts ??= new Fonts();
            var result = new List<object>();
            foreach (var item in props.GetProperty("fonts").EnumerateArray()) {
                var family = item.GetProperty("family").GetString()!;
                var variant = item.GetProperty("variant").GetString()!;
                var bytes = File.ReadAllBytes(item.GetProperty("file").GetString()!);
                var identity = System.Security.Cryptography.SHA256.HashData(bytes.Concat(System.Text.Encoding.UTF8.GetBytes(family + ":" + variant)).ToArray());
                var key = new Guid(identity.AsSpan(0, 16));
                // ECMA-376 font obfuscation uses reversed GUID bytes for the first 32 bytes.
                var mask = Convert.FromHexString(key.ToString("N")).Reverse().ToArray();
                for (var i = 0; i < Math.Min(32, bytes.Length); i++) bytes[i] ^= mask[i % 16];
                var fontPart = tablePart.AddNewPart<FontPart>("application/vnd.openxmlformats-officedocument.obfuscatedFont");
                using (var stream = new MemoryStream(bytes)) fontPart.FeedData(stream);
                var font = tablePart.Fonts.Elements<Font>().FirstOrDefault(f => f.Name?.Value == family);
                if (font == null) { font = new Font { Name = family }; tablePart.Fonts.Append(font); }
                OpenXmlElement reference = variant switch {
                    "regular" => new EmbedRegularFont(), "bold" => new EmbedBoldFont(),
                    "italic" => new EmbedItalicFont(), "boldItalic" => new EmbedBoldItalicFont(),
                    _ => throw new ArgumentException("INVALID_FONT_VARIANT") };
                var old = font.ChildElements.FirstOrDefault(e => e.LocalName == reference.LocalName);
                if (old != null) {
                    var previousId = old.GetAttribute("id", "http://schemas.openxmlformats.org/officeDocument/2006/relationships").Value;
                    font.RemoveChild(old);
                    if (!String.IsNullOrEmpty(previousId)) tablePart.DeletePart(previousId);
                }
                reference.SetAttribute(new OpenXmlAttribute("r", "id", "http://schemas.openxmlformats.org/officeDocument/2006/relationships", tablePart.GetIdOfPart(fontPart)));
                reference.SetAttribute(new OpenXmlAttribute("w", "fontKey", "http://schemas.openxmlformats.org/wordprocessingml/2006/main", key.ToString("B").ToUpperInvariant()));
                reference.SetAttribute(new OpenXmlAttribute("w", "subsetted", "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "0"));
                font.AddChild(reference, true);
                result.Add(new { family, variant, part = fontPart.Uri.ToString(), bytes = bytes.Length });
            }
            tablePart.Fonts.Save();
            return new { operation, applied = true, fonts = result };
        }
        throw new ArgumentException("SDK_LAYOUT_EXTENSION_UNSUPPORTED");
    }
}
