using System.Text.Json;
using Timetabling.Engine;

namespace Timetabling.Engine.Tests;

public class PyRandomTests
{
    static readonly Dictionary<string, JsonElement> Vectors = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(
        File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", "random_vectors.json")))!;

    public static IEnumerable<object[]> Seeds() => Vectors.Keys.Select(k => new object[] { k });

    static long[] Ints(JsonElement e) => e.EnumerateArray().Select(x => x.GetInt64()).ToArray();

    [Theory, MemberData(nameof(Seeds))]
    public void MatchesCPythonCallForCall(string seed)
    {
        var v = Vectors[seed];
        var rng = new PyRandom(ulong.Parse(seed));
        Assert.Equal(v.GetProperty("random").EnumerateArray().Select(x => x.GetDouble()), Enumerable.Range(0, 5).Select(_ => rng.Random()));
        Assert.Equal(Ints(v.GetProperty("getrandbits")), new[] { 0, 1, 7, 31, 32 }.Select(k => (long)rng.GetRandBits(k)));
        Assert.Equal(Ints(v.GetProperty("randrange")), new[] { 1, 2, 3, 17, 174, 1000, int.MaxValue }.Select(n => (long)rng.RandRange(n)));
        var items = Enumerable.Range(0, 30).ToList();
        rng.Shuffle(items);
        Assert.Equal(Ints(v.GetProperty("shuffle30")), items.Select(x => (long)x));
        Assert.Equal(Ints(v.GetProperty("choice")), new[] { 1, 5, 174 }.Select(n => (long)rng.Choice(Enumerable.Range(0, n).ToArray())));
        var samples = v.GetProperty("sample").EnumerateArray().Select(Ints).ToArray();
        var ns = new[] { 2, 5, 21, 22, 174 };
        for (var i = 0; i < ns.Length; i++)
            Assert.Equal(samples[i], rng.SampleRange(ns[i], 2).Select(x => (long)x));
        Assert.Equal(Ints(v.GetProperty("sample_k7")), rng.SampleRange(100, 7).Select(x => (long)x));
        var mixed = v.GetProperty("mixed").EnumerateArray().ToArray();
        for (var i = 0; i < mixed.Length; i++)
        {
            if (i % 3 == 0) Assert.Equal(mixed[i].GetDouble(), rng.Random());
            else Assert.Equal(mixed[i].GetInt64(), rng.RandRange(174));
        }
    }
}
