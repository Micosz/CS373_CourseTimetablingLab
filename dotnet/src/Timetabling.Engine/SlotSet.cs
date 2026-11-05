using System.Numerics;

namespace Timetabling.Engine;

/// <summary>A contiguous run of 5-minute slots across the term: what Python stores as one big-int bit mask.</summary>
public readonly record struct SlotRange(int Start, int Length)
{
    public const int SlotsPerDay = 288, SlotsPerWeek = 7 * SlotsPerDay;

    public static SlotRange Of(Meeting meeting, int week) =>
        new((week - 1) * SlotsPerWeek + meeting.Day * SlotsPerDay + meeting.StartMinute / 5, meeting.DurationMinutes / 5);
}

/// <summary>Fixed-size bitset of term slots; replaces Python's arbitrary-precision integer masks.</summary>
public sealed class SlotSet
{
    readonly ulong[] words;

    public SlotSet(int slots) => words = new ulong[(slots + 63) >> 6];

    public static SlotSet ForWeeks(int maxWeek) => new(Math.Max(1, maxWeek) * SlotRange.SlotsPerWeek);

    public void Clear() => Array.Clear(words);

    public bool IsEmpty => Array.TrueForAll(words, w => w == 0);

    public void Add(SlotRange r)
    {
        int start = r.Start, end = r.Start + r.Length;
        while (start < end)
        {
            int word = start >> 6, bit = start & 63, take = Math.Min(64 - bit, end - start);
            words[word] |= Mask(bit, take);
            start += take;
        }
    }

    public bool Intersects(SlotRange r)
    {
        int start = r.Start, end = r.Start + r.Length;
        while (start < end)
        {
            int word = start >> 6, bit = start & 63, take = Math.Min(64 - bit, end - start);
            if ((words[word] & Mask(bit, take)) != 0) return true;
            start += take;
        }
        return false;
    }

    public void UnionWith(SlotSet other)
    {
        var a = words; var b = other.words;
        for (var i = 0; i < a.Length; i++) a[i] |= b[i];
    }

    public void CopyFrom(SlotSet other) => Array.Copy(other.words, words, words.Length);

    public int Count
    {
        get { var n = 0; foreach (var w in words) n += BitOperations.PopCount(w); return n; }
    }

    static ulong Mask(int bit, int take) => take == 64 ? ulong.MaxValue : ((1UL << take) - 1) << bit;
}
