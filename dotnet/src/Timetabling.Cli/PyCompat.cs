using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Timetabling.Cli;

/// <summary>Small helpers that make C# output byte-compatible with what the Python tools write.</summary>
public static class PyCompat
{
    /// <summary>Python repr() of a float: shortest round-trip digits; scientific outside 1e-4 &lt;= |x| &lt; 1e16.</summary>
    public static string Float(double value)
    {
        if (double.IsNaN(value)) return "nan";
        if (double.IsInfinity(value)) return value > 0 ? "inf" : "-inf";
        var sign = value < 0 || (value == 0 && double.IsNegative(value)) ? "-" : "";
        if (value == 0) return sign + "0.0";
        var r = Math.Abs(value).ToString("R", CultureInfo.InvariantCulture);
        string digits;
        int exp10;
        if (r.Contains('E'))
        {
            var parts = r.Split('E');
            digits = parts[0].Replace(".", "");
            exp10 = int.Parse(parts[1], CultureInfo.InvariantCulture);
        }
        else
        {
            var dot = r.IndexOf('.');
            if (dot < 0) dot = r.Length;
            var all = r.Replace(".", "");
            var lead = 0;
            while (lead < all.Length - 1 && all[lead] == '0') lead++;
            digits = all[lead..];
            exp10 = dot - 1 - lead;
        }
        digits = digits.TrimEnd('0');
        if (digits.Length == 0) digits = "0";
        if (exp10 is >= -4 and < 16)
        {
            if (exp10 < 0) return sign + "0." + new string('0', -exp10 - 1) + digits;
            var whole = digits.Length > exp10 + 1 ? digits[..(exp10 + 1)] : digits.PadRight(exp10 + 1, '0');
            var frac = digits.Length > exp10 + 1 ? digits[(exp10 + 1)..] : "0";
            return sign + whole + "." + frac;
        }
        var mantissa = digits.Length > 1 ? digits[0] + "." + digits[1..] : digits;
        return sign + mantissa + "e" + (exp10 < 0 ? "-" : "+") + Math.Abs(exp10).ToString("00", CultureInfo.InvariantCulture);
    }

    public static string Bool(bool value) => value ? "True" : "False";

    /// <summary>json.dumps(value, sort_keys=True) with Python's default separators and ensure_ascii.</summary>
    public static string DumpsSorted(JsonNode? node)
    {
        var sb = new StringBuilder();
        Write(node, sb);
        return sb.ToString();
    }

    static void Write(JsonNode? node, StringBuilder sb)
    {
        switch (node)
        {
            case null: sb.Append("null"); break;
            case JsonObject obj:
                sb.Append('{');
                var first = true;
                foreach (var (key, value) in obj.OrderBy(p => p.Key, StringComparer.Ordinal))
                {
                    if (!first) sb.Append(", ");
                    first = false;
                    WriteString(key, sb);
                    sb.Append(": ");
                    Write(value, sb);
                }
                sb.Append('}');
                break;
            case JsonArray array:
                sb.Append('[');
                for (var i = 0; i < array.Count; i++)
                {
                    if (i > 0) sb.Append(", ");
                    Write(array[i], sb);
                }
                sb.Append(']');
                break;
            case JsonValue value:
                var element = value.GetValue<JsonElement>();
                switch (element.ValueKind)
                {
                    case JsonValueKind.String: WriteString(element.GetString()!, sb); break;
                    case JsonValueKind.True: sb.Append("true"); break;
                    case JsonValueKind.False: sb.Append("false"); break;
                    case JsonValueKind.Null: sb.Append("null"); break;
                    case JsonValueKind.Number:
                        var raw = element.GetRawText();
                        sb.Append(raw.IndexOfAny(['.', 'e', 'E']) >= 0 ? Float(element.GetDouble()) : raw);
                        break;
                    default: throw new InvalidDataException("Unsupported JSON value");
                }
                break;
        }
    }

    static void WriteString(string s, StringBuilder sb)
    {
        sb.Append('"');
        foreach (var ch in s)
        {
            switch (ch)
            {
                case '"': sb.Append("\\\""); break;
                case '\\': sb.Append("\\\\"); break;
                case '\n': sb.Append("\\n"); break;
                case '\r': sb.Append("\\r"); break;
                case '\t': sb.Append("\\t"); break;
                case '\b': sb.Append("\\b"); break;
                case '\f': sb.Append("\\f"); break;
                default:
                    if (ch < 0x20 || ch > 0x7e) sb.Append("\\u").Append(((int)ch).ToString("x4"));
                    else sb.Append(ch);
                    break;
            }
        }
        sb.Append('"');
    }

    public static string Sha256Hex(string text) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();

    /// <summary>uuid.uuid5(uuid.NAMESPACE_URL, name).</summary>
    public static Guid Uuid5Url(string name)
    {
        byte[] ns = [0x6b, 0xa7, 0xb8, 0x11, 0x9d, 0xad, 0x11, 0xd1, 0x80, 0xb4, 0x00, 0xc0, 0x4f, 0xd4, 0x30, 0xc8];
        var hash = SHA1.HashData([.. ns, .. Encoding.UTF8.GetBytes(name)]);
        var bytes = hash[..16];
        bytes[6] = (byte)((bytes[6] & 0x0f) | 0x50);
        bytes[8] = (byte)((bytes[8] & 0x3f) | 0x80);
        return new Guid(bytes, bigEndian: true);
    }

    public static string NowIso() => DateTimeOffset.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffffzzz", CultureInfo.InvariantCulture);

    /// <summary>Writes UTF-8 with BOM, like Python's encoding='utf-8-sig' used for the CSV files.</summary>
    public static StreamWriter CsvWriter(string path) => new(path, false, new UTF8Encoding(true)) { NewLine = "\r\n" };

    public static string CsvField(string? value) =>
        value is null ? "" : value.IndexOfAny([',', '"', '\n', '\r']) >= 0 ? "\"" + value.Replace("\"", "\"\"") + "\"" : value;
}
