using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;

if (Environment.GetEnvironmentVariable("GITHUB_ACTIONS") != "true" ||
    String.IsNullOrEmpty(Environment.GetEnvironmentVariable("GITHUB_RUN_ID")))
    throw new InvalidOperationException("CLOUD_ONLY");
if (args.Length < 2 || args[0] != "validate")
    throw new ArgumentException("Usage: WordSdk validate file.docx");
using var document = WordprocessingDocument.Open(args[1], false);
var validator = new OpenXmlValidator(FileFormatVersions.Office2021);
var errors = validator.Validate(document).Select(e => new {
    id = e.Id, description = e.Description, part = e.Part?.Uri.ToString(), path = e.Path?.XPath
}).ToList();
Console.WriteLine(JsonSerializer.Serialize(new { version = "3.4.1", target = "Office2021", errors }));
return errors.Count == 0 ? 0 : 2;
