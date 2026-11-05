using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Timetabling.Engine;

/// <summary>Reads a runner.py config object into <see cref="RunConfig"/> with Python's defaults and conversions.</summary>
static class RunConfigReader
{
    public static RunConfig Read(JsonObject config)
    {
        // type(budget) is not int: a JSON float such as 100.0, a bool or a string is rejected.
        int budget = 100;
        if (config.TryGetPropertyValue("budget", out var b))
        {
            if (b is not JsonValue || Element(b) is not { ValueKind: JsonValueKind.Number } be || !be.TryGetInt64(out var whole))
                throw new ArgumentException("Evaluation budget must be an integer from 1 to 100000");
            budget = (int)Math.Clamp(whole, int.MinValue, int.MaxValue);
        }
        double seconds = 60;
        if (config.TryGetPropertyValue("seconds", out var s))
        {
            if (s is not JsonValue || Element(s) is not { ValueKind: JsonValueKind.Number } se)
                throw new ArgumentException("Time limit must be 1..3600 seconds per run");
            seconds = se.GetDouble();
        }
        var roomMode = RoomModes.Weekly;
        if (config.TryGetPropertyValue("room_mode", out var m))
        {
            if (m is not JsonValue || Element(m) is not { ValueKind: JsonValueKind.String } me) throw new ArgumentException("Room mode must be weekly or fixed");
            roomMode = me.GetString()!;
        }
        var given = config.TryGetPropertyValue("parameters", out var p) ? p as JsonObject ?? throw new ArgumentException("parameters must be an object") : [];
        JsonObject Section(string name) =>
            given.TryGetPropertyValue(name, out var node) ? node as JsonObject ?? throw new ArgumentException($"parameters.{name} must be an object") : [];
        JsonObject hc = Section("hc"), sa = Section("sa"), ga = Section("ga");
        var parameters = new MethodParameters
        {
            Hc = new HcParameters(Int(hc, "restart_patience", 20)),
            Sa = new SaParameters(Float(sa, "initial_acceptance", 0.8), Float(sa, "cooling_rate", 0.97)),
            Ga = new GaParameters(Int(ga, "population_size", 12), Int(ga, "tournament_size", 3), Float(ga, "mutation_rate", 0.3),
                                  Float(ga, "crossover_rate", 0.9), Int(ga, "elites", 1)),
        };
        return new RunConfig(budget, seconds, roomMode, parameters) { ParametersJson = (JsonObject)given.DeepClone() };
    }

    /// <summary>A JsonValue built in code (JsonValue&lt;int&gt;) or parsed from text, read the same way.</summary>
    static JsonElement Element(JsonNode? node) => JsonSerializer.SerializeToElement(node);

    /// <summary>Python int(): integers as they are, floats truncated toward zero, integer strings parsed.</summary>
    static int Int(JsonObject section, string key, int fallback)
    {
        if (!section.TryGetPropertyValue(key, out var node)) return fallback;
        var e = Element(node);
        double value = e.ValueKind == JsonValueKind.Number ? e.GetDouble()
            : e.ValueKind == JsonValueKind.String && long.TryParse(e.GetString()!.Trim(), NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out var parsed) ? parsed
            : e.ValueKind is JsonValueKind.True or JsonValueKind.False ? (e.GetBoolean() ? 1 : 0)
            : throw new ArgumentException($"Parameter {key} must be an integer");
        if (!double.IsFinite(value)) throw new ArgumentException($"Parameter {key} must be an integer");
        return (int)Math.Clamp(Math.Truncate(value), int.MinValue, int.MaxValue);
    }

    /// <summary>Python float(): numbers, bools and numeric strings.</summary>
    static double Float(JsonObject section, string key, double fallback)
    {
        if (!section.TryGetPropertyValue(key, out var node)) return fallback;
        var e = Element(node);
        return e.ValueKind == JsonValueKind.Number ? e.GetDouble()
            : e.ValueKind == JsonValueKind.String && double.TryParse(e.GetString()!.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed) ? parsed
            : e.ValueKind is JsonValueKind.True or JsonValueKind.False ? (e.GetBoolean() ? 1 : 0)
            : throw new ArgumentException($"Parameter {key} must be a number");
    }
}
