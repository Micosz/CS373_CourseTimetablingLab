using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using Timetabling.Engine;

namespace RoomMap;

/// <summary>App shell: header, view switcher, and the Room map / Live run / Compare views.</summary>
public partial class Main : Control
{
    readonly ConcurrentQueue<Action> mainThread = new();
    void Post(Action action) => mainThread.Enqueue(action);

    string? repoRoot;
    LoadedDataset? dataset;
    ExperimentFile? experiment;
    Schedule? greedyWeekly, greedyFixed, liveSchedule;
    readonly Dictionary<string, Schedule> runSchedules = [];
    CancellationTokenSource? liveCancel;
    bool liveRunning;

    // Header
    Label datasetPill = null!, experimentPill = null!, toast = null!;
    readonly List<Button> navButtons = [];
    readonly List<Control> pages = [];
    FileDialog? fileDialog;

    // Room map view
    OptionButton mapSource = null!, mapMode = null!, mapMethod = null!, mapSeed = null!;
    WeekControls mapControls = null!;
    RoomMapView mapView = null!;
    WeekBars mapBars = null!;
    Label mapTitle = null!, mapCheck = null!, weekLine = null!, detailText = null!, stripInfo = null!;
    Label mUnassigned = null!, mLab = null!, mChanges = null!;
    SessionStrip strip = null!;

    // Live run view
    OptionButton liveMethod = null!, liveMode = null!;
    SpinBox liveSeed = null!, liveBudget = null!;
    Button runButton = null!, cancelButton = null!, openLiveInMap = null!;
    ProgressBar liveProgress = null!;
    Label liveStatus = null!, liveParams = null!;
    ObjectiveChart chart = null!;
    WeekControls liveControls = null!;
    RoomMapView liveView = null!;

    // Compare view
    OptionButton cmpMethod = null!, cmpSeed = null!;
    Label cmpSource = null!, cmpStory = null!;
    WeekControls cmpControls = null!;
    RoomMapView cmpWeekly = null!, cmpFixed = null!;
    WeekBars cmpWeeklyBars = null!, cmpFixedBars = null!;
    readonly Label[,] cmpValues = new Label[3, 2];
    readonly Label[] cmpDelta = new Label[3];

    public override void _Ready()
    {
        var args = OS.GetCmdlineUserArgs();
        repoRoot = RepoLocator.Root(ProjectSettings.GlobalizePath("res://"), Path.GetDirectoryName(OS.GetExecutablePath()) ?? "");
        if (args.Contains("--smoke"))
        {
            var code = SmokeTest.Run(repoRoot, s => GD.Print(s));
            GetTree().Quit(code);
            return;
        }
        Theme = Ui.BuildTheme();
        BuildUi();
        StartLoading();
        var capture = args.FirstOrDefault(a => a.StartsWith("--capture="));
        if (capture is not null) _ = Capture(capture["--capture=".Length..]);
    }

    public override void _Process(double delta)
    {
        while (mainThread.TryDequeue(out var action)) action();
    }

    // ---- loading -----------------------------------------------------------------------------------------------

    void StartLoading()
    {
        var datasetPath = RepoLocator.DefaultDataset(repoRoot);
        if (datasetPath is null)
        {
            datasetPill.Text = "ไม่พบ data/fall-cs.json.gz · เปิดไฟล์ dataset เอง";
            return;
        }
        datasetPill.Text = "กำลังโหลด dataset…";
        var finalPath = RepoLocator.FinalExperiment(repoRoot);
        Task.Run(() =>
        {
            try
            {
                var ds = LoadedDataset.Load(datasetPath);
                currentSha = ds.Index.Sha256;
                Post(() => OnDataset(ds));
                DecodeGreedy(ds);
                if (finalPath is not null) LoadExperiment(finalPath);
            }
            catch (Exception ex) { Post(() => Toast("โหลดไม่สำเร็จ: " + ex.Message, true)); }
        });
    }

    void DecodeGreedy(LoadedDataset ds)
    {
        var p = ds.Problem;
        var weekly = p.Decode(p.InitialGenome(), null, RoomModes.Weekly);
        var fixedC = p.Decode(p.InitialGenome(), null, RoomModes.Fixed);
        Post(() =>
        {
            if (dataset != ds) return;
            greedyWeekly = new Schedule(ds.Index, weekly.Solution, RoomModes.Weekly, "greedy", 0, "Greedy decode · weekly");
            greedyFixed = new Schedule(ds.Index, fixedC.Solution, RoomModes.Fixed, "greedy", 0, "Greedy decode · fixed");
            RefreshPickers();
            if (mapSource.Selected != 0 || experiment is null) { mapSource.Selected = 1; ApplyMapSource(false); }
            ApplyCompare();
        });
    }

    void LoadExperiment(string path)
    {
        Post(() => experimentPill.Text = "กำลังโหลด " + Path.GetFileName(Path.GetDirectoryName(path)) + "…");
        var loaded = DataFileLoader.Load(path);
        if (loaded is LoadedDataset ds)
        {
            currentSha = ds.Index.Sha256;
            Post(() => OnDataset(ds));
            DecodeGreedy(ds);
            return;
        }
        var exp = (ExperimentFile)loaded;
        // An experiment carries its dataset; switch to it if it is not the one already loaded.
        LoadedDataset? own = null;
        if (exp.DatasetText is { } text && Dataset.Sha256(text) != currentSha)
        {
            own = LoadedDataset.FromText(path + " (dataset_text)", text);
            currentSha = own.Index.Sha256;
        }
        Post(() =>
        {
            if (own is not null) OnDataset(own);
            OnExperiment(exp);
        });
        if (own is not null) DecodeGreedy(own);
    }

    /// <summary>Sha of the dataset loaded or being loaded (set on the loader thread, before it is posted).</summary>
    volatile string? currentSha;

    void OnDataset(LoadedDataset ds)
    {
        dataset = ds;
        runSchedules.Clear();
        greedyWeekly = greedyFixed = liveSchedule = null;
        var d = ds.Data;
        datasetPill.Text = $"{Path.GetFileName(ds.Path)} · {d.Classes.Count} วิชา · {d.RecurringSessions.Count} sessions · {ds.Index.TotalWeekly:#,0} ครั้ง/เทอม · {ds.Index.Rooms.Length} ห้อง ({ds.Index.LabCount} Lab)";
        foreach (var c in new[] { mapControls, liveControls, cmpControls })
        {
            c.SetDays(ds.Index.Days);
            c.SetWeeks(ds.Index.Weeks);
        }
        if (experiment is not null && experiment.DatasetText is { } t && Dataset.Sha256(t) != ds.Index.Sha256)
        {
            experiment = null;
            experimentPill.Text = "ไม่มีผลการทดลอง · no experiment";
        }
        mapSource.SetItemDisabled(2, true);
        openLiveInMap.Disabled = true;
        runButton.Disabled = liveRunning;
        RefreshPickers();
    }

    void OnExperiment(ExperimentFile exp)
    {
        experiment = exp;
        runSchedules.Clear();
        experimentPill.Text = $"{exp.Name} · {exp.Runs.Count} runs";
        liveParams.Text = exp.Parameters is null ? "พารามิเตอร์: ค่าเริ่มต้นของ engine" : "พารามิเตอร์: ค่าที่จูนแล้วจาก " + exp.Name;
        RefreshPickers();
        mapSource.Selected = 0;
        ApplyMapSource(true);
        ApplyCompare();
        Toast($"โหลด {exp.Runs.Count} runs จาก {Path.GetFileName(exp.Path)} แล้ว");
    }

    void OpenFile()
    {
        fileDialog ??= MakeFileDialog();
        if (repoRoot is not null) fileDialog.CurrentDir = Path.Combine(repoRoot, "experiments");
        fileDialog.PopupCentered(new Vector2I(1000, 640));
    }

    FileDialog MakeFileDialog()
    {
        var d = new FileDialog
        {
            FileMode = FileDialog.FileModeEnum.OpenFile,
            Access = FileDialog.AccessEnum.Filesystem,
            UseNativeDialog = true,
            Title = "เปิด experiment หรือ dataset (.json / .json.gz)",
            Filters = ["*.json.gz, *.json ; Experiment or dataset"],
        };
        d.FileSelected += path =>
        {
            Toast("กำลังโหลด " + path);
            Task.Run(() =>
            {
                try { LoadExperiment(path); }
                catch (Exception ex) { Post(() => Toast("เปิดไฟล์ไม่สำเร็จ: " + ex.Message, true)); }
            });
        };
        AddChild(d);
        return d;
    }

    // ---- layout ------------------------------------------------------------------------------------------------

    void BuildUi()
    {
        var bg = new ColorRect { Color = Palette.Background };
        bg.SetAnchorsPreset(LayoutPreset.FullRect);
        AddChild(bg);
        var margin = new MarginContainer();
        margin.SetAnchorsPreset(LayoutPreset.FullRect);
        foreach (var side in new[] { "left", "right", "top", "bottom" }) margin.AddThemeConstantOverride("margin_" + side, 16);
        AddChild(margin);
        var root = Ui.VBox(12);
        margin.AddChild(root);

        // Header card.
        datasetPill = Ui.Text("…", 13, Palette.TealDark);
        experimentPill = Ui.Text("ไม่มีผลการทดลอง · no experiment", 13, Palette.InkSoft);
        var titleBox = Ui.VBox(2,
            Ui.Text("แผนที่ห้องรายสัปดาห์ · Weekly Room Map", 24, Palette.TealDark, bold: true),
            Ui.Text("Lab ถูกจองเฉพาะสัปดาห์ที่ต้องใช้จริง (weekly) เทียบกับถือห้องเดิมทั้งเทอม (fixed)", 13, Palette.InkSoft));
        var pills = Ui.VBox(4, Pill(datasetPill, Palette.TealWash), Pill(experimentPill, Palette.SkyWash));
        var header = Ui.HBox(16, titleBox, Ui.Spacer(), pills, Ui.Button("📂  เปิดไฟล์… Open", "PrimaryButton", OpenFile));
        root.AddChild(Ui.Card(header));

        // View switcher.
        var nav = Ui.HBox(8);
        var group = new ButtonGroup();
        string[] names = ["🗺  แผนที่ห้อง Room map", "⚡  รันสด Live run", "⚖  เปรียบเทียบ Compare"];
        for (var i = 0; i < names.Length; i++)
        {
            var b = Ui.Button(names[i]);
            b.ToggleMode = true;
            b.ButtonGroup = group;
            var index = i;
            b.Pressed += () => ShowPage(index);
            navButtons.Add(b);
            nav.AddChild(b);
        }
        nav.AddChild(Ui.Spacer());
        toast = Ui.Text("", 13, Palette.TealDark);
        nav.AddChild(toast);
        root.AddChild(nav);

        var stack = Ui.Expand(new Control(), true, true);
        root.AddChild(stack);
        foreach (var page in new[] { BuildMapPage(), BuildLivePage(), BuildComparePage() })
        {
            page.SetAnchorsPreset(LayoutPreset.FullRect);
            stack.AddChild(page);
            pages.Add(page);
        }
        ShowPage(0);
    }

    static PanelContainer Pill(Label label, Color bg)
    {
        var p = new PanelContainer();
        var sb = Ui.Box(bg, 999, null, 0, 0);
        sb.ContentMarginLeft = sb.ContentMarginRight = 12;
        sb.ContentMarginTop = sb.ContentMarginBottom = 3;
        p.AddThemeStyleboxOverride("panel", sb);
        p.AddChild(label);
        return p;
    }

    void ShowPage(int index)
    {
        for (var i = 0; i < pages.Count; i++)
        {
            pages[i].Visible = i == index;
            navButtons[i].SetPressedNoSignal(i == index);
        }
    }

    void Toast(string text, bool warning = false)
    {
        toast.Text = text;
        toast.AddThemeColorOverride("font_color", warning ? Palette.Coral : Palette.TealDark);
    }

    static (PanelContainer Tile, Label Value) Metric(string title, Color color, string unit)
    {
        var value = Ui.Text("–", 26, color, bold: true);
        var box = Ui.VBox(0, Ui.Text(title, 12, Palette.InkSoft), value, Ui.Text(unit, 11, Palette.InkSoft));
        return (Ui.Card(box, "InnerCard"), value);
    }

    static Control Legend()
    {
        var box = Ui.VBox(6, Ui.Text("สี · Legend", 14, Palette.Ink, bold: true));
        foreach (var s in new[] { BlockState.LabNeeded, BlockState.LabUnnecessary, BlockState.Lecture, BlockState.External, BlockState.Unavailable, BlockState.Unassigned })
        {
            var swatch = new Panel { CustomMinimumSize = new Vector2(26, 16) };
            swatch.AddThemeStyleboxOverride("panel", s == BlockState.Unassigned
                ? Ui.Box(Palette.Cream, 5, null, 0, 0, Palette.Coral, 2)
                : Ui.Box(Palette.Of(s), 5, s == BlockState.LabUnnecessary ? new Color(Palette.Coral, 0.5f) : null, 3, 0, s == BlockState.Unavailable ? Palette.Stone : null, 1));
            swatch.SizeFlagsVertical = SizeFlags.ShrinkCenter;
            box.AddChild(Ui.HBox(8, swatch, Ui.Text(Palette.Name(s), 12)));
        }
        return Ui.Card(box);
    }

    // ---- Room map page -----------------------------------------------------------------------------------------

    Control BuildMapPage()
    {
        mapSource = Ui.Options("ผลการทดลอง Experiment", "Greedy (decode ตอนนี้)", "ผลรันสด Live run");
        mapSource.SetItemDisabled(0, true);
        mapSource.SetItemDisabled(2, true);
        mapMode = Ui.Options("weekly", "fixed");
        mapMethod = Ui.Options("greedy");
        mapSeed = Ui.Options("–");
        foreach (var o in new[] { mapSource, mapMode, mapMethod, mapSeed })
        {
            Ui.Expand(o);
            o.ItemSelected += _ => ApplyMapSource(true);
        }
        mapCheck = Ui.Text("", 12, Palette.InkSoft, wrap: true);
        var source = Ui.VBox(8,
            Ui.Text("แหล่งตาราง · Schedule", 14, Palette.Ink, bold: true),
            mapSource,
            Ui.HBox(6, Ui.Text("โหมด", 12, Palette.InkSoft), mapMode),
            Ui.HBox(6, Ui.Text("วิธี", 12, Palette.InkSoft), mapMethod),
            Ui.HBox(6, Ui.Text("seed", 12, Palette.InkSoft), mapSeed),
            mapCheck);

        (var t1, mUnassigned) = Metric("ไม่ได้ห้อง", Palette.Coral, "sessions/เทอม");
        (var t2, mLab) = Metric("Lab ไม่จำเป็น", Palette.Coral, "ชั่วโมง/เทอม");
        (var t3, mChanges) = Metric("เปลี่ยนห้อง", Palette.Sky, "ครั้ง/เทอม");
        foreach (var t in new[] { t1, t2, t3 }) Ui.Expand(t);
        weekLine = Ui.Text("", 12, Palette.TealDark, wrap: true);
        var metrics = Ui.VBox(8, Ui.Text("ผลรวม · Totals", 14, Palette.Ink, bold: true), Ui.HBox(6, t1, t2, t3), weekLine);

        detailText = Ui.Text("ชี้หรือคลิกบล็อกเพื่อดูรายละเอียด\nHover or click a block.", 12, Palette.Ink, wrap: true);
        strip = new SessionStrip();
        stripInfo = Ui.Text("", 11, Palette.InkSoft, wrap: true);
        var detail = Ui.VBox(6, Ui.Text("รายละเอียด · Details", 14, Palette.Ink, bold: true), detailText, strip, stripInfo);

        var side = Ui.VBox(12, Ui.Card(source), Ui.Card(metrics), Ui.Card(detail), Legend());
        side.CustomMinimumSize = new Vector2(330, 0);
        var sideScroll = new ScrollContainer { HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled, CustomMinimumSize = new Vector2(352, 0) };
        side.SizeFlagsHorizontal = SizeFlags.ExpandFill;
        sideScroll.AddChild(side);

        mapTitle = Ui.Text("", 16, Palette.TealDark, bold: true);
        mapControls = new WeekControls();
        mapView = Ui.Expand(new RoomMapView(), true, true);
        mapBars = Ui.Expand(new WeekBars());
        mapControls.Changed += (w, d) => OnMapWeek(w, d);
        mapBars.WeekPicked += w => mapControls.SetWeek(w);
        mapView.HoverChanged += b => ShowDetail(b ?? SelectedBlock());
        mapView.BlockClicked += b => { ShowDetail(b); ShowStrip(b.SessionId); };
        var main = Ui.Expand(Ui.Card(Ui.VBox(10, mapTitle, mapControls, mapView, mapBars)), true, true);
        return Ui.HBox(14, sideScroll, main);
    }

    Block? SelectedBlock() =>
        mapView.Schedule is { } s && mapView.SelectedSession is { } id
            ? s.Blocks(mapView.Week, mapView.Day).FirstOrDefault(b => b.SessionId == id) : null;

    void OnMapWeek(int week, int day)
    {
        mapView.SetWeekDay(week, day);
        mapBars.Week = week;
        mapBars.QueueRedraw();
        strip.Week = week;
        strip.QueueRedraw();
        UpdateWeekLine();
        ShowDetail(SelectedBlock());
    }

    void UpdateWeekLine()
    {
        if (mapView.Schedule is not { } s) { weekLine.Text = ""; return; }
        var w = s.PerWeek.FirstOrDefault(x => x.Week == mapView.Week);
        if (w is null) return;
        weekLine.Text = $"สัปดาห์ {w.Week}: Lab ที่ต้องใช้ {Ui.Hours(w.LabNeededMinutes / 60.0)} ชม. · Lab ไม่จำเป็น {Ui.Hours(w.LabUnnecessaryMinutes / 60.0)} ชม. · ไม่ได้ห้อง {w.Unassigned}";
    }

    void ShowDetail(Block? b)
    {
        if (b is null || mapView.Schedule is null) { detailText.Text = "ชี้หรือคลิกบล็อกเพื่อดูรายละเอียด\nHover or click a block."; return; }
        detailText.Text = RoomMapView.Describe(mapView.Schedule, b);
    }

    void ShowStrip(string? sessionId)
    {
        strip.Schedule = mapView.Schedule;
        strip.SessionId = sessionId;
        strip.Week = mapView.Week;
        strip.QueueRedraw();
        if (sessionId is null || mapView.Schedule is not { } s || !s.Index.Sessions.TryGetValue(sessionId, out var session)) { stripInfo.Text = ""; return; }
        var rooms = session.ActiveWeeks.Select(w => s.RoomOf(sessionId, w)).Where(r => r is not null).Distinct().Count();
        var wasted = session.ActiveWeeks.Count(w => s.StateOf(session, w, s.RoomOf(sessionId, w)) == BlockState.LabUnnecessary);
        stripInfo.Text = $"{sessionId}: ใช้ {rooms} ห้อง · เปลี่ยนห้อง {s.ChangesOf(sessionId)} ครั้ง · ถือ Lab โดยไม่จำเป็น {wasted} สัปดาห์ (• = สัปดาห์ที่ต้องใช้ Lab)";
    }

    void RefreshPickers()
    {
        var exp = experiment;
        mapSource.SetItemDisabled(0, exp is null);
        mapSource.SetItemDisabled(1, greedyWeekly is null);
        Fill(mapMethod, exp?.Methods.ToArray() ?? ["greedy"], Ui.MethodName);
        Fill(mapSeed, exp?.Seeds.Select(s => s.ToString()).ToArray() ?? ["–"], s => s);
        Fill(cmpMethod, exp?.Methods.ToArray() ?? ["greedy"], Ui.MethodName);
        Fill(cmpSeed, exp?.Seeds.Select(s => s.ToString()).ToArray() ?? ["–"], s => s);
        cmpSource.Text = exp is null ? "แหล่ง: decode greedy ด้วย engine ตอนนี้" : "แหล่ง: " + exp.Name;
    }

    static void Fill(OptionButton o, string[] values, Func<string, string> label)
    {
        var current = o.Selected >= 0 && o.Selected < o.ItemCount ? o.GetItemMetadata(o.Selected).AsString() : null;
        o.Clear();
        for (var i = 0; i < values.Length; i++)
        {
            o.AddItem(label(values[i]));
            o.SetItemMetadata(i, values[i]);
        }
        var keep = Array.IndexOf(values, current);
        o.Selected = keep >= 0 ? keep : 0;
    }

    static string Value(OptionButton o) => o.Selected >= 0 && o.ItemCount > 0 ? o.GetItemMetadata(o.Selected).AsString() : "";

    Schedule? ScheduleFor(string mode, string method, string seedText)
    {
        if (experiment is null || dataset is null || !ulong.TryParse(seedText, out var seed)) return null;
        var key = $"{mode}/{method}/{seed}";
        if (runSchedules.TryGetValue(key, out var s)) return s;
        var run = experiment.Find(mode, method, seed);
        if (run is null) return null;
        s = new Schedule(dataset.Index, run.Solution, mode, method, seed, $"{Ui.MethodName(method)} · {mode} · seed {seed}");
        runSchedules[key] = s;
        return s;
    }

    void ApplyMapSource(bool animate)
    {
        var source = mapSource.Selected;
        var mode = mapMode.Selected == 1 ? RoomModes.Fixed : RoomModes.Weekly;
        mapMethod.Disabled = mapSeed.Disabled = source != 0;
        mapMode.Disabled = source == 2;
        Schedule? s = source switch
        {
            0 => ScheduleFor(mode, Value(mapMethod), Value(mapSeed)),
            1 => mode == RoomModes.Fixed ? greedyFixed : greedyWeekly,
            _ => liveSchedule,
        };
        mapView.SetSchedule(s, animate);
        mapBars.Schedule = s;
        mapBars.QueueRedraw();
        mapTitle.Text = s is null ? "ไม่มีตารางสำหรับตัวเลือกนี้" : s.Title + "  ·  " + Ui.ModeName(s.RoomMode);
        mUnassigned.Text = s is null ? "–" : s.Unassigned.ToString("#,0");
        mLab.Text = s is null ? "–" : Ui.Hours(s.UnnecessaryLabHours);
        mChanges.Text = s is null ? "–" : s.RoomChanges.ToString("#,0");
        mapCheck.Text = "";
        if (s is not null && source == 0 && experiment?.Find(s.RoomMode, s.Algorithm, s.Seed)?.Metrics is { } m)
        {
            var ok = m.Unassigned == s.Unassigned && m.UnnecessaryLabMinutes == s.UnnecessaryLabMinutes && m.RoomChanges == s.RoomChanges;
            mapCheck.Text = ok ? "✓ คำนวณใหม่ตรงกับ metrics ในไฟล์" : $"≠ ไฟล์บอก {m.Unassigned} / {m.UnnecessaryLabMinutes / 60.0:0.#} ชม. / {m.RoomChanges}";
            mapCheck.AddThemeColorOverride("font_color", ok ? Palette.TealDark : Palette.Coral);
        }
        UpdateWeekLine();
        ShowDetail(SelectedBlock());
        ShowStrip(mapView.SelectedSession);
    }

    // ---- Live run page -----------------------------------------------------------------------------------------

    Control BuildLivePage()
    {
        liveMethod = Ui.Options();
        foreach (var m in Algorithms.Names) liveMethod.AddItem(Ui.MethodName(m));
        liveMethod.Selected = 1;
        liveMode = Ui.Options("weekly", "fixed");
        liveSeed = new SpinBox { MinValue = 0, MaxValue = uint.MaxValue, Step = 1, Value = 1001, Rounded = true };
        liveBudget = new SpinBox { MinValue = 1, MaxValue = 100000, Step = 1, Value = 100, Rounded = true, Suffix = "evals" };
        foreach (var c in new Control[] { liveMethod, liveMode, liveSeed, liveBudget }) Ui.Expand(c);
        runButton = Ui.Button("▶  เริ่มค้นหา Run", "PrimaryButton", StartLive);
        cancelButton = Ui.Button("■  ยกเลิก Cancel", "DangerButton", () => liveCancel?.Cancel());
        cancelButton.Disabled = true;
        runButton.Disabled = true;
        liveProgress = new ProgressBar { MinValue = 0, MaxValue = 100, CustomMinimumSize = new Vector2(0, 16), ShowPercentage = false };
        liveStatus = Ui.Text("พร้อม · ready", 13, Palette.InkSoft, wrap: true);
        liveParams = Ui.Text("พารามิเตอร์: ค่าเริ่มต้นของ engine", 11, Palette.InkSoft, wrap: true);
        openLiveInMap = Ui.Button("🗺  เปิดในแผนที่ห้อง", "", () =>
        {
            mapSource.SetItemDisabled(2, false);
            mapSource.Selected = 2;
            ApplyMapSource(true);
            ShowPage(0);
        });
        openLiveInMap.Disabled = true;
        var form = Ui.VBox(10,
            Ui.Text("ค้นหาสด · Live search", 16, Palette.TealDark, bold: true),
            Ui.Text("รัน engine C# บนเธรดพื้นหลังด้วย SearchContext + Algorithms (ผลเหมือน Python ทุกบิต)", 12, Palette.InkSoft, wrap: true),
            Row("วิธี method", liveMethod), Row("seed", liveSeed), Row("budget", liveBudget), Row("โหมดห้อง", liveMode),
            Ui.HBox(8, Ui.Expand(runButton), Ui.Expand(cancelButton)),
            liveProgress, liveStatus, liveParams, openLiveInMap);
        var formCard = Ui.Card(form);
        formCard.CustomMinimumSize = new Vector2(330, 0);

        chart = Ui.Expand(new ObjectiveChart());
        liveControls = new WeekControls();
        liveView = Ui.Expand(new RoomMapView(), true, true);
        liveControls.Changed += (w, d) => liveView.SetWeekDay(w, d);
        var chartCard = Ui.Card(Ui.VBox(8, Ui.Text("ค่าที่ดีที่สุดตาม evaluations · Best objectives", 14, Palette.Ink, bold: true), chart));
        var mapCard = Ui.Expand(Ui.Card(Ui.VBox(8, Ui.Text("ตารางสุดท้าย · Final schedule", 14, Palette.Ink, bold: true), liveControls, liveView)), true, true);
        return Ui.HBox(14, Ui.VBox(0, formCard), Ui.Expand(Ui.VBox(12, chartCard, mapCard), true, true));
    }

    static Control Row(string label, Control field)
    {
        var l = Ui.Text(label, 12, Palette.InkSoft);
        l.CustomMinimumSize = new Vector2(84, 0);
        return Ui.HBox(8, l, field);
    }

    void StartLive()
    {
        if (dataset is null || liveRunning) return;
        var ds = dataset;
        var method = Algorithms.Names[liveMethod.Selected];
        var mode = liveMode.Selected == 1 ? RoomModes.Fixed : RoomModes.Weekly;
        var seed = (ulong)liveSeed.Value;
        var budget = (int)liveBudget.Value;
        var parameters = experiment?.Parameters ?? new MethodParameters();
        liveCancel = new CancellationTokenSource();
        var token = liveCancel.Token;
        liveRunning = true;
        runButton.Disabled = true;
        cancelButton.Disabled = false;
        chart.Clear();
        chart.Budget = budget;
        liveProgress.MaxValue = budget;
        liveProgress.Value = 0;
        liveStatus.Text = $"กำลังค้นหา {Ui.MethodName(method)} · {mode} · seed {seed}…";
        Task.Run(() =>
        {
            var context = new SearchContext(ds.Problem, seed, budget, 24 * 3600, e => Post(() => OnProgress(e)), mode, token);
            string status = "completed";
            try
            {
                context.Initial = context.Evaluate(ds.Problem.InitialGenome());
                Algorithms.Run(method, ds.Problem, context, parameters);
            }
            catch (SearchStoppedException stop) { status = stop.Reason; }
            catch (Exception ex) { status = "error: " + ex.Message; }
            var trace = context.Trace.ToList();
            var best = context.Best;
            var seconds = context.Elapsed;
            var evaluations = context.Evaluations;
            Post(() => OnLiveFinished(ds, method, mode, seed, status, best, trace, evaluations, seconds));
        });
    }

    void OnProgress(ProgressEvent e)
    {
        if (!liveRunning) return;
        chart.Add(e.Evaluations, e.Best.ToArray(), e.Current.ToArray());
        liveProgress.Value = e.Evaluations;
        liveStatus.Text = $"{e.Evaluations}/{e.Budget} evals · {e.Seconds:0.0} s · ดีที่สุด {e.Best.Unassigned} ไม่ได้ห้อง · {Ui.Hours(e.Best.LabMinutes / 60.0)} ชม. Lab ไม่จำเป็น · {e.Best.RoomChanges} เปลี่ยนห้อง";
    }

    void OnLiveFinished(LoadedDataset ds, string method, string mode, ulong seed, string status, Candidate? best,
                        List<TracePoint> trace, int evaluations, double seconds)
    {
        liveRunning = false;
        runButton.Disabled = dataset is null;
        cancelButton.Disabled = true;
        chart.Clear();
        foreach (var p in trace) chart.Add(p.Evaluations, p.Objectives, p.CurrentObjectives);
        liveProgress.Value = evaluations;
        var reason = status switch
        {
            "evaluation_budget" => "ครบ budget", "cancelled" => "ยกเลิกแล้ว", "completed" => "เสร็จ", "time_limit" => "หมดเวลา", _ => status,
        };
        if (best is null || dataset != ds)
        {
            liveStatus.Text = $"{reason} · ยังไม่มีผล ({evaluations} evals)";
            return;
        }
        liveSchedule = new Schedule(ds.Index, best.Solution, mode, method, seed, $"รันสด {Ui.MethodName(method)} · seed {seed}");
        liveView.SetSchedule(liveSchedule, true);
        mapSource.SetItemDisabled(2, false);
        openLiveInMap.Disabled = false;
        var o = best.Objectives;
        liveStatus.Text = $"{reason} · {evaluations} evals · {seconds:0.0} s\nดีที่สุด: ไม่ได้ห้อง {o.Unassigned} · Lab ไม่จำเป็น {Ui.Hours(o.LabMinutes / 60.0)} ชม. · เปลี่ยนห้อง {o.RoomChanges}";
        if (mapSource.Selected == 2) ApplyMapSource(true);
    }

    // ---- Compare page ------------------------------------------------------------------------------------------

    Control BuildComparePage()
    {
        cmpMethod = Ui.Options("greedy");
        cmpSeed = Ui.Options("–");
        cmpMethod.ItemSelected += _ => ApplyCompare();
        cmpSeed.ItemSelected += _ => ApplyCompare();
        cmpSource = Ui.Text("", 12, Palette.InkSoft);
        cmpStory = Ui.Text("", 15, Palette.White, bold: true, wrap: true);
        var picker = Ui.HBox(10, Ui.Text("วิธี", 13, Palette.InkSoft), cmpMethod, Ui.Text("seed", 13, Palette.InkSoft), cmpSeed, cmpSource);
        picker.Alignment = BoxContainer.AlignmentMode.Begin;

        string[] titles = ["Lab ไม่จำเป็น (ชม./เทอม)", "ไม่ได้ห้อง (sessions)", "เปลี่ยนห้อง (ครั้ง)"];
        var tiles = Ui.HBox(12);
        for (var k = 0; k < 3; k++)
        {
            cmpValues[k, 0] = Ui.Text("–", 26, Palette.TealDark, bold: true);
            cmpValues[k, 1] = Ui.Text("–", 26, Palette.Coral, bold: true);
            cmpDelta[k] = Ui.Text("", 12, Palette.InkSoft);
            var values = Ui.HBox(18,
                Ui.VBox(0, Ui.Text("weekly", 11, Palette.InkSoft), cmpValues[k, 0]),
                Ui.VBox(0, Ui.Text("fixed", 11, Palette.InkSoft), cmpValues[k, 1]));
            tiles.AddChild(Ui.Expand(Ui.Card(Ui.VBox(2, Ui.Text(titles[k], 13, Palette.Ink, bold: true), values, cmpDelta[k]), "InnerCard")));
        }
        var story = Ui.Card(cmpStory, "HeroCard");
        story.CustomMinimumSize = new Vector2(360, 0);
        tiles.AddChild(story);

        cmpControls = new WeekControls();
        (var weeklyCard, cmpWeekly, cmpWeeklyBars) = CompareMap("weekly · เปลี่ยนห้องได้รายสัปดาห์", Palette.TealDark);
        (var fixedCard, cmpFixed, cmpFixedBars) = CompareMap("fixed · ห้องเดิมทั้งเทอม", Palette.Coral);
        cmpControls.Changed += (w, d) =>
        {
            cmpWeekly.SetWeekDay(w, d);
            cmpFixed.SetWeekDay(w, d);
            cmpWeeklyBars.Week = cmpFixedBars.Week = w;
            cmpWeeklyBars.QueueRedraw();
            cmpFixedBars.QueueRedraw();
        };
        // Selecting a session in one map highlights it in both.
        cmpWeekly.BlockClicked += b => { cmpFixed.SelectedSession = b.SessionId; cmpFixed.QueueRedraw(); };
        cmpFixed.BlockClicked += b => { cmpWeekly.SelectedSession = b.SessionId; cmpWeekly.QueueRedraw(); };
        cmpWeeklyBars.WeekPicked += w => cmpControls.SetWeek(w);
        cmpFixedBars.WeekPicked += w => cmpControls.SetWeek(w);
        var maps = Ui.Expand(Ui.HBox(12, weeklyCard, fixedCard), true, true);
        return Ui.VBox(12, Ui.Card(Ui.VBox(10, picker, tiles)), Ui.Card(cmpControls), maps);
    }

    static (Control, RoomMapView, WeekBars) CompareMap(string title, Color color)
    {
        var view = Ui.Expand(new RoomMapView { Compact = true }, true, true);
        view.CustomMinimumSize = new Vector2(400, 260);
        var bars = Ui.Expand(new WeekBars());
        bars.CustomMinimumSize = new Vector2(300, 84);
        var card = Ui.Expand(Ui.Card(Ui.VBox(6, Ui.Text(title, 15, color, bold: true), view, bars)), true, true);
        return (card, view, bars);
    }

    void ApplyCompare()
    {
        Schedule? weekly, fixedS;
        if (experiment is not null)
        {
            weekly = ScheduleFor(RoomModes.Weekly, Value(cmpMethod), Value(cmpSeed));
            fixedS = ScheduleFor(RoomModes.Fixed, Value(cmpMethod), Value(cmpSeed));
        }
        else { weekly = greedyWeekly; fixedS = greedyFixed; }
        cmpWeekly.SetSchedule(weekly, true);
        cmpFixed.SetSchedule(fixedS, true);
        var max = new[] { weekly, fixedS }.Where(s => s is not null)
            .SelectMany(s => s!.PerWeek).Select(w => (w.LabNeededMinutes + w.LabUnnecessaryMinutes) / 60.0).DefaultIfEmpty(1).Max();
        foreach (var (bars, s) in new[] { (cmpWeeklyBars, weekly), (cmpFixedBars, fixedS) })
        {
            bars.Schedule = s;
            bars.SharedMaxHours = max;
            bars.QueueRedraw();
        }
        if (weekly is null || fixedS is null) { cmpStory.Text = "เลือกวิธีและ seed ที่มีทั้งสองโหมด"; return; }
        (double W, double F, string Unit)[] rows =
        [
            (weekly.UnnecessaryLabHours, fixedS.UnnecessaryLabHours, "ชม."),
            (weekly.Unassigned, fixedS.Unassigned, "sessions"),
            (weekly.RoomChanges, fixedS.RoomChanges, "ครั้ง"),
        ];
        for (var k = 0; k < 3; k++)
        {
            cmpValues[k, 0].Text = Ui.Hours(rows[k].W);
            cmpValues[k, 1].Text = Ui.Hours(rows[k].F);
            var d = rows[k].F - rows[k].W;
            cmpDelta[k].Text = d == 0 ? "เท่ากัน" : $"fixed {(d > 0 ? "มากกว่า" : "น้อยกว่า")} {Ui.Hours(Math.Abs(d))} {rows[k].Unit}";
        }
        var labDiff = fixedS.UnnecessaryLabHours - weekly.UnnecessaryLabHours;
        cmpStory.Text = labDiff > 0
            ? $"โหมด fixed ถือ Lab ไว้โดยไม่ได้ใช้มากกว่า {Ui.Hours(labDiff)} ชม./เทอม\nweekly คืน Lab ในสัปดาห์ที่ไม่ต้องใช้ แลกกับการเปลี่ยนห้อง {weekly.RoomChanges:#,0} ครั้ง"
            : $"สองโหมดใช้ Lab โดยไม่จำเป็นต่างกัน {Ui.Hours(labDiff)} ชม.";
    }

    // ---- screenshots -------------------------------------------------------------------------------------------

    async Task Wait(double seconds) => await ToSignal(GetTree().CreateTimer(seconds), SceneTreeTimer.SignalName.Timeout);

    async Task Capture(string dir)
    {
        if (!Path.IsPathRooted(dir)) dir = Path.Combine(ProjectSettings.GlobalizePath("res://"), dir);
        Directory.CreateDirectory(dir);
        DisplayServer.WindowSetSize(new Vector2I(1600, 900));
        var waited = 0.0;
        while ((experiment is null || greedyWeekly is null) && waited < 180) { await Wait(0.2); waited += 0.2; }
        await Wait(0.5);

        // Room map: weekly greedy, Tuesday of a Lab week, with a session that changes room selected.
        mapControls.SetDay(1);
        mapControls.SetWeek(5);
        var s = mapView.Schedule!;
        var pick = s.Blocks(5, 1).Where(b => b.SessionId is not null && b.RoomId is not null)
            .OrderByDescending(b => s.ChangesOf(b.SessionId!)).ThenBy(b => b.State == BlockState.LabNeeded ? 0 : 1).First();
        mapView.SelectedSession = pick.SessionId;
        ShowDetail(pick);
        ShowStrip(pick.SessionId);
        await Wait(1.5);
        Save(dir, "room-map.png");

        // Live run: a short hill-climbing search.
        ShowPage(1);
        liveMethod.Selected = 1;
        liveBudget.Value = 300;
        liveControls.SetDay(1);
        liveControls.SetWeek(5);
        StartLive();
        waited = 0;
        while (liveRunning && waited < 300) { await Wait(0.2); waited += 0.2; }
        await Wait(1.5);
        Save(dir, "live-run.png");

        // Compare: weekly vs fixed for greedy, same week and day.
        ShowPage(2);
        cmpControls.SetDay(1);
        cmpControls.SetWeek(5);
        await Wait(1.5);
        Save(dir, "compare.png");
        GetTree().Quit();
    }

    void Save(string dir, string name)
    {
        var image = GetViewport().GetTexture().GetImage();
        var path = Path.Combine(dir, name);
        image.SavePng(path);
        GD.Print("saved " + path);
    }
}
