namespace Timetabling.Engine.Tests;

/// <summary>Locates repository files (data/, experiments/) from the test output directory.</summary>
public static class RepoPaths
{
    public static readonly string Root = Find();

    static string Find()
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, "data", "provenance.json"))) return dir.FullName;
        throw new DirectoryNotFoundException("Repository root with data/provenance.json not found");
    }

    public static string Of(params string[] parts) => Path.Combine([Root, .. parts]);

    static readonly Lazy<(Dataset Data, Problem Problem)> main = new(() =>
    {
        var data = Dataset.Parse(Dataset.ReadText(Of("data", "fall-cs.json.gz")));
        return (data, new Problem(data));
    });

    public static Dataset MainDataset => main.Value.Data;
    public static Problem MainProblem => main.Value.Problem;
}
