using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using Timetabling.Engine;

namespace RoomMap;

/// <summary>Day pills, a week slider and play/step buttons that animate the weeks.</summary>
public partial class WeekControls : HBoxContainer
{
    public event Action<int, int>? Changed; // week, day

    public int Week { get; private set; } = 1;
    public int Day { get; private set; }
    public bool Playing { get; private set; }

    int[] weeks = Enumerable.Range(1, 15).ToArray();
    readonly HSlider slider = new() { MinValue = 1, MaxValue = 15, Step = 1, Value = 1, CustomMinimumSize = new Vector2(220, 24) };
    readonly Label weekLabel = Ui.Text("สัปดาห์ 1 / 15", 15, Palette.TealDark, bold: true);
    readonly HBoxContainer dayBox = Ui.HBox(4);
    readonly Button play;
    readonly OptionButton speed = Ui.Options("ช้า 1.6s", "ปกติ 0.9s", "เร็ว 0.45s");
    double elapsed;
    bool quiet;

    public WeekControls()
    {
        AddThemeConstantOverride("separation", 8);
        Alignment = AlignmentMode.Begin;
        AddChild(dayBox);
        AddChild(new VSeparator());
        AddChild(Ui.Button("◀", "", () => Step(-1)));
        slider.SizeFlagsVertical = SizeFlags.ShrinkCenter;
        slider.SizeFlagsHorizontal = SizeFlags.ExpandFill;
        slider.ValueChanged += v => { if (!quiet) SetWeek(weeks[Math.Clamp((int)v - 1, 0, weeks.Length - 1)]); };
        AddChild(slider);
        AddChild(Ui.Button("▶", "", () => Step(1)));
        weekLabel.CustomMinimumSize = new Vector2(124, 0);
        weekLabel.HorizontalAlignment = HorizontalAlignment.Center;
        AddChild(weekLabel);
        play = Ui.Button("▶  เล่น Play", "PrimaryButton", TogglePlay);
        play.CustomMinimumSize = new Vector2(124, 0);
        AddChild(play);
        speed.Selected = 1;
        AddChild(speed);
        SetDays([0, 1, 2, 3, 4]);
    }

    public void SetDays(int[] days)
    {
        foreach (var c in dayBox.GetChildren()) c.QueueFree();
        var group = new ButtonGroup();
        foreach (var d in days)
        {
            var b = Ui.Button(Ui.Day(d), "ChipButton");
            b.ToggleMode = true;
            b.ButtonGroup = group;
            b.ButtonPressed = d == Day;
            var day = d;
            b.Pressed += () => { Day = day; Changed?.Invoke(Week, Day); };
            dayBox.AddChild(b);
        }
        if (!days.Contains(Day) && days.Length > 0) { Day = days[0]; ((Button)dayBox.GetChild(0)).ButtonPressed = true; }
    }

    public void SetWeeks(int[] ids)
    {
        weeks = ids.Length > 0 ? ids : [1];
        quiet = true;
        slider.MaxValue = weeks.Length;
        quiet = false;
        if (!weeks.Contains(Week)) Week = weeks[0];
        Refresh();
    }

    public void SetWeek(int week, bool notify = true)
    {
        Week = week;
        Refresh();
        if (notify) Changed?.Invoke(Week, Day);
    }

    public void SetDay(int day)
    {
        Day = day;
        foreach (var c in dayBox.GetChildren())
            if (c is Button b) b.SetPressedNoSignal(b.Text == Ui.Day(day));
        Changed?.Invoke(Week, Day);
    }

    void Refresh()
    {
        var i = Array.IndexOf(weeks, Week);
        quiet = true;
        slider.Value = i + 1;
        quiet = false;
        weekLabel.Text = $"สัปดาห์ {Week} / {weeks[^1]}";
    }

    public void Step(int by)
    {
        var i = Array.IndexOf(weeks, Week);
        SetWeek(weeks[((i + by) % weeks.Length + weeks.Length) % weeks.Length]);
    }

    void TogglePlay()
    {
        Playing = !Playing;
        play.Text = Playing ? "❚❚  หยุด Pause" : "▶  เล่น Play";
        elapsed = 0;
    }

    public override void _Process(double delta)
    {
        if (!Playing) return;
        elapsed += delta;
        var interval = speed.Selected switch { 0 => 1.6, 2 => 0.45, _ => 0.9 };
        if (elapsed >= interval) { elapsed = 0; Step(1); }
    }
}

/// <summary>Per-week Lab hours: needed (teal) stacked under unnecessary (coral). Clicking a bar jumps to that week.</summary>
public partial class WeekBars : Control
{
    public event Action<int>? WeekPicked;
    public Schedule? Schedule { get; set; }
    public int Week { get; set; } = 1;
    public double SharedMaxHours { get; set; }

    public WeekBars()
    {
        CustomMinimumSize = new Vector2(300, 96);
        MouseFilter = MouseFilterEnum.Stop;
        TooltipText = " ";
    }

    double MaxHours => SharedMaxHours > 0 ? SharedMaxHours :
        Math.Max(1, Schedule?.PerWeek.Max(w => (w.LabNeededMinutes + w.LabUnnecessaryMinutes) / 60.0) ?? 1);

    Rect2 BarRect(int i, WeekStats w, out float needH)
    {
        var n = Schedule!.PerWeek.Length;
        float left = 150, width = Size.X - left - 4, slot = width / n, bottom = Size.Y - 18, height = bottom - 16;
        var total = (w.LabNeededMinutes + w.LabUnnecessaryMinutes) / 60.0;
        var h = (float)(total / MaxHours) * height;
        needH = (float)(w.LabNeededMinutes / 60.0 / MaxHours) * height;
        return new Rect2(left + i * slot + slot * 0.18f, bottom - h, slot * 0.64f, h);
    }

    public override void _Draw()
    {
        if (Schedule is null) return;
        var font = Ui.Regular;
        DrawString(Ui.Bold, new Vector2(0, 30), "ชั่วโมง Lab ต่อสัปดาห์", HorizontalAlignment.Left, 150, 13, Palette.Ink);
        DrawString(font, new Vector2(0, 50), "■ ต้องใช้ needed", HorizontalAlignment.Left, 150, 12, Palette.Teal);
        DrawString(font, new Vector2(0, 68), "■ ไม่จำเป็น unnecessary", HorizontalAlignment.Left, 150, 12, Palette.Coral);
        var bottom = Size.Y - 18;
        DrawLine(new Vector2(150, bottom), new Vector2(Size.X - 4, bottom), Palette.Line, 1);
        for (var i = 0; i < Schedule.PerWeek.Length; i++)
        {
            var w = Schedule.PerWeek[i];
            var rect = BarRect(i, w, out var needH);
            if (w.Week == Week) DrawStyleBox(Ui.Box(new Color(Palette.Gold, 0.35f), 6, new Color(Palette.Gold, 0.45f), 6, 0), rect.Grow(3));
            var need = new Rect2(rect.Position.X, rect.End.Y - needH, rect.Size.X, needH);
            var extra = new Rect2(rect.Position.X, rect.Position.Y, rect.Size.X, rect.Size.Y - needH);
            if (need.Size.Y > 0) DrawStyleBox(Ui.Box(Palette.Teal, 4, null, 0, 0), need);
            if (extra.Size.Y > 0.5f) DrawStyleBox(Ui.Box(Palette.Coral, 4, new Color(Palette.Coral, 0.4f), 3, 0), extra);
            var current = w.Week == Week;
            if (current) DrawStyleBox(Ui.Box(new Color(0, 0, 0, 0), 6, null, 0, 0, Palette.Gold, 3), rect.Grow(3));
            DrawString(current ? Ui.Bold : font, new Vector2(rect.Position.X + rect.Size.X / 2 - 7, Size.Y - 3), w.Week.ToString(),
                HorizontalAlignment.Left, -1, 11, current ? Palette.TealDark : Palette.InkSoft);
        }
    }

    int? WeekAt(Vector2 at)
    {
        if (Schedule is null) return null;
        for (var i = 0; i < Schedule.PerWeek.Length; i++)
        {
            var r = BarRect(i, Schedule.PerWeek[i], out _);
            if (at.X >= r.Position.X - 4 && at.X <= r.End.X + 4 && at.Y >= 10) return i;
        }
        return null;
    }

    public override void _GuiInput(InputEvent e)
    {
        if (e is InputEventMouseButton { Pressed: true, ButtonIndex: MouseButton.Left } click && WeekAt(click.Position) is int i)
            WeekPicked?.Invoke(Schedule!.PerWeek[i].Week);
    }

    public override string _GetTooltip(Vector2 at)
    {
        if (WeekAt(at) is not int i) return "";
        var w = Schedule!.PerWeek[i];
        return $"สัปดาห์ week {w.Week}\nLab ที่ต้องใช้ needed: {Ui.Hours(w.LabNeededMinutes / 60.0)} ชม.\nLab ไม่จำเป็น unnecessary: {Ui.Hours(w.LabUnnecessaryMinutes / 60.0)} ชม.\nไม่ได้ห้อง unassigned: {w.Unassigned} sessions";
    }
}

/// <summary>The rooms one session holds across all weeks, coloured by state.</summary>
public partial class SessionStrip : Control
{
    public Schedule? Schedule { get; set; }
    public string? SessionId { get; set; }
    public int Week { get; set; }

    public SessionStrip() => CustomMinimumSize = new Vector2(240, 58);

    public override void _Draw()
    {
        if (Schedule is null || SessionId is null || !Schedule.Index.Sessions.TryGetValue(SessionId, out var s)) return;
        var weeks = Schedule.Index.Weeks;
        var cell = Size.X / weeks.Length;
        for (var i = 0; i < weeks.Length; i++)
        {
            var week = weeks[i];
            var rect = new Rect2(i * cell + 1, 4, cell - 2, 30);
            if (!s.ActiveWeeks.Contains(week))
            {
                DrawStyleBox(Ui.Box(Palette.StoneWash, 5, null, 0, 0), rect);
            }
            else
            {
                var room = Schedule.RoomOf(s.Id, week);
                var state = Schedule.StateOf(s, week, room);
                DrawStyleBox(state == BlockState.Unassigned ? Ui.Box(Palette.Cream, 5, null, 0, 0, Palette.Coral, 2) : Ui.Box(Palette.Of(state), 5, null, 0, 0), rect);
                if (room is not null && cell > 26)
                {
                    var tag = room.StartsWith("SIM-LAB-") ? "L" + room[^1] : room.TrimStart('R');
                    DrawString(Ui.Regular, new Vector2(rect.Position.X + 2, rect.Position.Y + 19), tag, HorizontalAlignment.Center, rect.Size.X - 4, 10,
                        state == BlockState.Lecture ? Palette.Ink : Palette.White);
                }
                if (s.LabWeeks.Contains(week))
                    DrawCircle(new Vector2(rect.Position.X + rect.Size.X / 2, rect.End.Y + 5), 2.5f, Palette.TealDark);
            }
            if (week == Week) DrawStyleBox(Ui.Box(new Color(0, 0, 0, 0), 6, null, 0, 0, Palette.Gold, 2), rect.Grow(2));
            DrawString(Ui.Regular, new Vector2(rect.Position.X, Size.Y - 2), week.ToString(), HorizontalAlignment.Center, rect.Size.X, 10, Palette.InkSoft);
        }
    }
}

/// <summary>Best objectives (lines) and current candidate objectives (dots) over evaluations.</summary>
public partial class ObjectiveChart : Control
{
    public readonly List<(int Evaluations, long[] Best, long[] Current)> Points = [];
    public int Budget { get; set; } = 100;

    static readonly (string Title, Color Color, double Scale)[] Series =
    [
        ("ไม่ได้ห้อง unassigned", Palette.Coral, 1),
        ("Lab ไม่จำเป็น (ชม.) unnecessary h", Palette.Teal, 1 / 60.0),
        ("เปลี่ยนห้อง room changes", Palette.Sky, 1),
    ];

    public ObjectiveChart() => CustomMinimumSize = new Vector2(600, 170);

    public void Clear() { Points.Clear(); QueueRedraw(); }

    public void Add(int evaluations, long[] best, long[] current)
    {
        Points.Add((evaluations, best, current));
        QueueRedraw();
    }

    public override void _Draw()
    {
        var gap = 14f;
        var w = (Size.X - gap * 2) / 3;
        for (var k = 0; k < 3; k++)
            DrawSeries(new Rect2(k * (w + gap), 0, w, Size.Y), k);
    }

    void DrawSeries(Rect2 area, int k)
    {
        var (title, color, scale) = Series[k];
        DrawStyleBox(Ui.Box(Palette.White, 14, null, 0, 0, Palette.Line, 1), area);
        DrawString(Ui.Bold, area.Position + new Vector2(12, 22), title, HorizontalAlignment.Left, area.Size.X - 24, 13, Palette.Ink);
        if (Points.Count == 0)
        {
            DrawString(Ui.Regular, area.Position + new Vector2(12, 48), "ยังไม่มีข้อมูล · run a search", HorizontalAlignment.Left, -1, 12, Palette.InkSoft);
            return;
        }
        var last = Points[^1].Best[k] * scale;
        DrawString(Ui.Bold, area.Position + new Vector2(12, 50), Ui.Hours(last), HorizontalAlignment.Left, -1, 24, color);
        var plot = new Rect2(area.Position.X + 12, area.Position.Y + 62, area.Size.X - 24, area.Size.Y - 78);
        var values = Points.SelectMany(p => new[] { p.Best[k] * scale, p.Current[k] * scale }).ToList();
        double lo = values.Min(), hi = values.Max();
        if (hi - lo < 1e-9) { hi = lo + 1; lo -= 0; }
        var maxX = Math.Max(Budget, Points[^1].Evaluations);
        Vector2 At(int x, double v) => new(plot.Position.X + (float)(x / (double)Math.Max(1, maxX)) * plot.Size.X,
            plot.End.Y - (float)((v - lo) / (hi - lo)) * plot.Size.Y);
        DrawLine(new Vector2(plot.Position.X, plot.End.Y), new Vector2(plot.End.X, plot.End.Y), Palette.Line, 1);
        DrawString(Ui.Regular, new Vector2(plot.Position.X, area.End.Y - 4), Ui.Hours(lo), HorizontalAlignment.Left, -1, 10, Palette.InkSoft);
        DrawString(Ui.Regular, new Vector2(plot.Position.X, plot.Position.Y - 2), Ui.Hours(hi), HorizontalAlignment.Left, -1, 10, Palette.InkSoft);
        DrawString(Ui.Regular, new Vector2(plot.End.X - 60, area.End.Y - 4), $"{maxX} evals", HorizontalAlignment.Right, 60, 10, Palette.InkSoft);
        foreach (var p in Points)
            DrawCircle(At(p.Evaluations, p.Current[k] * scale), 2f, new Color(color, 0.28f));
        var line = new List<Vector2>();
        foreach (var p in Points)
        {
            var pt = At(p.Evaluations, p.Best[k] * scale);
            if (line.Count > 0) line.Add(new Vector2(pt.X, line[^1].Y)); // step: best only changes on improvement
            line.Add(pt);
        }
        if (line.Count == 1) line.Add(line[0] + new Vector2(2, 0));
        DrawPolyline(line.ToArray(), new Color(color, 0.25f), 7, true);
        DrawPolyline(line.ToArray(), color, 2.5f, true);
        DrawCircle(line[^1], 4, Palette.Gold);
    }
}
