namespace Timetabling.Engine;

/// <summary>
/// Bit-exact port of CPython's <c>random.Random</c> (MT19937) for the calls the engine makes.
/// The same integer seed gives the same sequence as <c>random.Random(seed)</c> in Python 3,
/// so a C# run reproduces a Python run exactly.
/// </summary>
public sealed class PyRandom
{
    const int N = 624, M = 397;
    const uint MatrixA = 0x9908b0dfu, UpperMask = 0x80000000u, LowerMask = 0x7fffffffu;
    readonly uint[] mt = new uint[N];
    int mti = N + 1;

    public PyRandom(ulong seed)
    {
        // CPython splits abs(seed) into 32-bit words, least significant first; 0 becomes [0].
        var key = new List<uint>();
        var n = seed;
        do { key.Add((uint)n); n >>= 32; } while (n != 0);
        InitByArray(key);
    }

    void InitGenrand(uint s)
    {
        mt[0] = s;
        for (mti = 1; mti < N; mti++)
            mt[mti] = 1812433253u * (mt[mti - 1] ^ (mt[mti - 1] >> 30)) + (uint)mti;
    }

    void InitByArray(IReadOnlyList<uint> key)
    {
        InitGenrand(19650218u);
        int i = 1, j = 0, length = key.Count;
        for (var k = Math.Max(N, length); k > 0; k--)
        {
            mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525u)) + key[j] + (uint)j;
            i++; j++;
            if (i >= N) { mt[0] = mt[N - 1]; i = 1; }
            if (j >= length) j = 0;
        }
        for (var k = N - 1; k > 0; k--)
        {
            mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941u)) - (uint)i;
            i++;
            if (i >= N) { mt[0] = mt[N - 1]; i = 1; }
        }
        mt[0] = 0x80000000u;
    }

    uint NextUInt32()
    {
        uint y;
        if (mti >= N)
        {
            int kk;
            for (kk = 0; kk < N - M; kk++)
            {
                y = (mt[kk] & UpperMask) | (mt[kk + 1] & LowerMask);
                mt[kk] = mt[kk + M] ^ (y >> 1) ^ ((y & 1u) != 0 ? MatrixA : 0u);
            }
            for (; kk < N - 1; kk++)
            {
                y = (mt[kk] & UpperMask) | (mt[kk + 1] & LowerMask);
                mt[kk] = mt[kk + (M - N)] ^ (y >> 1) ^ ((y & 1u) != 0 ? MatrixA : 0u);
            }
            y = (mt[N - 1] & UpperMask) | (mt[0] & LowerMask);
            mt[N - 1] = mt[M - 1] ^ (y >> 1) ^ ((y & 1u) != 0 ? MatrixA : 0u);
            mti = 0;
        }
        y = mt[mti++];
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c5680u;
        y ^= (y << 15) & 0xefc60000u;
        y ^= y >> 18;
        return y;
    }

    /// <summary><c>random.random()</c>: a 53-bit float in [0, 1).</summary>
    public double Random()
    {
        uint a = NextUInt32() >> 5, b = NextUInt32() >> 6;
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
    }

    /// <summary><c>random.getrandbits(k)</c> for 0 &lt;= k &lt;= 32.</summary>
    public uint GetRandBits(int k)
    {
        if (k < 0 || k > 32) throw new ArgumentOutOfRangeException(nameof(k));
        return k == 0 ? 0u : NextUInt32() >> (32 - k);
    }

    /// <summary><c>random._randbelow(n)</c>: rejection sampling on bit_length(n) bits.</summary>
    public int RandBelow(int n)
    {
        if (n <= 0) throw new ArgumentOutOfRangeException(nameof(n));
        var k = 32 - System.Numerics.BitOperations.LeadingZeroCount((uint)n);
        var r = GetRandBits(k);
        while (r >= (uint)n) r = GetRandBits(k);
        return (int)r;
    }

    /// <summary><c>random.randrange(n)</c>.</summary>
    public int RandRange(int n) => n > 0 ? RandBelow(n) : throw new ArgumentException("empty range for randrange()");

    /// <summary><c>random.choice(seq)</c>.</summary>
    public T Choice<T>(IReadOnlyList<T> items) =>
        items.Count > 0 ? items[RandBelow(items.Count)] : throw new IndexOutOfRangeException("Cannot choose from an empty sequence");

    /// <summary><c>random.shuffle(x)</c> in place.</summary>
    public void Shuffle<T>(IList<T> items)
    {
        for (var i = items.Count - 1; i > 0; i--)
        {
            var j = RandBelow(i + 1);
            (items[i], items[j]) = (items[j], items[i]);
        }
    }

    /// <summary><c>random.sample(range(n), k)</c>, including CPython's switch between its pool and set strategies.</summary>
    public int[] SampleRange(int n, int k)
    {
        if (k < 0 || k > n) throw new ArgumentException("Sample larger than population or is negative");
        var result = new int[k];
        var setsize = 21;
        if (k > 5) setsize += (int)Math.Pow(4, Math.Ceiling(Math.Log(k * 3, 4)));
        if (n <= setsize)
        {
            var pool = Enumerable.Range(0, n).ToArray();
            for (var i = 0; i < k; i++)
            {
                var j = RandBelow(n - i);
                result[i] = pool[j];
                pool[j] = pool[n - i - 1];
            }
        }
        else
        {
            var selected = new HashSet<int>();
            for (var i = 0; i < k; i++)
            {
                var j = RandBelow(n);
                while (selected.Contains(j)) j = RandBelow(n);
                selected.Add(j);
                result[i] = j;
            }
        }
        return result;
    }
}
