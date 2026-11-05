using System.Text.Json.Nodes;
using Timetabling.Cli;

namespace Timetabling.Engine.Tests;

/// <summary>The CLI writes files the Python tools read; these values come from CPython (see comments).</summary>
public class CliCompatTests
{
    [Theory]
    [InlineData(0.1, "0.1")]
    [InlineData(1925.0, "1925.0")]
    [InlineData(57.7, "57.7")]
    [InlineData(1e-05, "1e-05")]
    [InlineData(1e16, "1e+16")]
    [InlineData(123456789.123, "123456789.123")]
    [InlineData(3600.0, "3600.0")]
    [InlineData(2.5e-7, "2.5e-07")]
    [InlineData(1.0 / 3, "0.3333333333333333")]
    public void FloatMatchesPythonRepr(double value, string repr) => Assert.Equal(repr, PyCompat.Float(value));

    [Fact]
    public void Uuid5MatchesPython() => // uuid.uuid5(uuid.NAMESPACE_URL, '/repo/results/final')
        Assert.Equal("6f225e6d-9f7a-514a-8268-583f5f30aa24", PyCompat.Uuid5Url("/repo/results/final").ToString());

    [Fact]
    public void SortedDumpMatchesPythonJsonDumps() =>
        // CPython: json.dumps({...}, sort_keys=True); ensure_ascii escapes the Thai text.
        Assert.Equal(@"{""algorithm"": ""ga"", ""name"": ""\u0e44\u0e17\u0e22 \""q\"""", ""parameters"": {""mutation_rate"": 0.66, ""population_size"": 35}, ""seconds"": 3600.0, ""seed"": 1001}",
            PyCompat.DumpsSorted(JsonNode.Parse("{\"seed\":1001,\"seconds\":3600.0,\"algorithm\":\"ga\",\"parameters\":{\"population_size\":35,\"mutation_rate\":0.66},\"name\":\"ไทย \\\"q\\\"\"}")));

    [Fact]
    public void JobsAndKeysFollowBatchPy()
    {
        var jobs = Batch.BuildJobs(["greedy", "ga"], ["weekly", "fixed"], [1001UL, 1002UL], 500, 3600, []);
        Assert.Equal(8, jobs.Count);
        Assert.Equal("main__weekly__greedy__1001", jobs[0].Key);
        Assert.Equal("main__fixed__ga__1002", jobs[^1].Key);
    }
}
