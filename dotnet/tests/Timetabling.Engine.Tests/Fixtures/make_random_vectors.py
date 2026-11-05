"""Write random_vectors.json: reference output of CPython's random module for PyRandom tests.

    python dotnet/tests/Timetabling.Engine.Tests/Fixtures/make_random_vectors.py
"""
import json
import random
from pathlib import Path

SEEDS = [0, 1, 42, 1001, 20261027, 2**32 - 1, 2**40 + 7]


def script(rng):
    out = {'random': [rng.random() for _ in range(5)],
           'getrandbits': [rng.getrandbits(k) for k in (0, 1, 7, 31, 32)],
           'randrange': [rng.randrange(n) for n in (1, 2, 3, 17, 174, 1000, 2**31 - 1)]}
    items = list(range(30))
    rng.shuffle(items)
    out['shuffle30'] = items
    out['choice'] = [rng.choice(range(n)) for n in (1, 5, 174)]
    out['sample'] = [rng.sample(range(n), 2) for n in (2, 5, 21, 22, 174)]
    out['sample_k7'] = rng.sample(range(100), 7)
    out['mixed'] = [rng.random() if i % 3 == 0 else rng.randrange(174) for i in range(2000)]
    return out


def main():
    vectors = {str(seed): script(random.Random(seed)) for seed in SEEDS}
    path = Path(__file__).with_name('random_vectors.json')
    path.write_text(json.dumps(vectors, indent=1) + '\n', encoding='utf-8')
    print('Saved', path)


if __name__ == '__main__':
    main()
