# Week 6 – Code Review and AI Agent Evaluation

**Repository:** https://github.com/Ezzgiturann/week6-habit-tracker
**Coding agent:** Claude Code (one-shot prompt per feature, run in a fresh session)
**AI reviewer:** CodeRabbit
**Tasks:** #1 Streak ([PR #1](https://github.com/Ezzgiturann/week6-habit-tracker/pull/1)) · #2 Validation ([PR #2](https://github.com/Ezzgiturann/week6-habit-tracker/pull/2))

Each PR starts with a commit holding the agent's one-shot output exactly as produced. My review fixes and the fixes for CodeRabbit's findings follow as separate commits, so the PR history shows who found what.

## 1. Guardrail Setup

- **Tools and commands:**
  - `ruff check .` (lint)
  - `black --check .` (format)
  - `pytest` (tests)
  - `./check.sh` runs all three in order and exits non-zero on the first failure.
  - Install with `pip install -r requirements-dev.txt`.
- **Guardrails configured:**
  - `pyproject.toml` configures ruff rules E, W, F, I, B and UP, with an 88-character line length, matching black.
  - `.github/workflows/ci.yml` runs `check.sh` on every push to `main` and on every pull request.
  - Tool versions are pinned in `requirements-dev.txt` (`black==25.11.0`, `ruff==0.17.5`).
- **How the checks were performed:**
  - **The unmodified starter failed both linters.** ruff reported 2 × E501 (lines over 88 characters) in `main.py`, and `black --check` would have reformatted `main.py`. Running `black .` fixed both.
  - **A deliberately failing test broke the build.** Adding `assert 1 + 1 == 3` made `./check.sh` exit with code 1 (`1 failed, 3 passed`). Removing it brought the exit code back to 0.
  - **CI failed twice before it passed:**
    - Python 3.9 is not available on GitHub's Ubuntu runner, so CI moved to 3.12.
    - `black --check` then passed locally but failed in CI. CI had installed black 26.10.1 and my machine had 25.11.0, and the two versions format code differently. After pinning the versions, CI went green.

## 2. Pull Request Reviews

CodeRabbit reviewed each PR after my review fixes had been pushed, so it saw the reviewed code, not the agent's original output.

### PR 1 – Streak

Commits:
- [`6992083`](https://github.com/Ezzgiturann/week6-habit-tracker/commit/6992083766e01d7952bb7fd0d7e0c7583c315c51): agent output
- [`b60b616`](https://github.com/Ezzgiturann/week6-habit-tracker/commit/b60b616083b1397f24e57a6ea7a8eee099296e9f): review fix
- [`1e9addc`](https://github.com/Ezzgiturann/week6-habit-tracker/commit/1e9addcb180a0132655e8c32af3d925d179be76d): review fix
- [`86f9966`](https://github.com/Ezzgiturann/week6-habit-tracker/commit/86f9966c26ffde224c91bf758c2e7a6a1ed48dcc): CodeRabbit fix

| Review Finding | My Review | CodeRabbit Review |
|---|---|---|
| Invalid date handling | The agent claimed `"2026-3-1"` and `"2026-03-01"` would count as the same day. I ran `date.fromisoformat('2026-3-1')` and got `ValueError`, so the claim was false: that check-in was dropped. **Fixed** in `b60b616`. | **Found something I missed.** On Python 3.11+, `fromisoformat` also accepts `20260314` and week dates (`2026-W11-6`). Those rows were counted on CI (3.12) but rejected on my machine (3.9), which contradicted the docstring from my own fix. **Fixed** in `86f9966`. Without the fix, the new test fails on 3.12. |
| Silent skipping | `except ValueError: continue` dropped bad rows with no signal, so the streak broke silently. **Fixed:** each skipped row is now logged with its value. | Hardening proposal (not a bug): logging every rejected value on every request lets user-controlled input grow the logs. It suggested bounded or aggregated diagnostics. **Not applied.** |
| Test coverage | Every rule in my prompt has a test: 404, today, yesterday fallback, zero, duplicates, gap, future dates, pinned clock. The agent also added month-boundary and insertion-order tests. **But the tests wrote into the real `habits.db`:** +12 habits per run, which showed up in `GET /habits`. **Fixed** in `1e9addc` with a `tmp_path` fixture. | Suggested a regression test for `["2026-03-15", "20260314"]`, which I added (parametrized with 4 forms). It did not mention database isolation, because that was already fixed when it reviewed. |
| Code quality | Naming and API shape are fine: `get_today` is an overridable dependency, `compute_streak` is a pure function, and the response matches the example in my prompt. | Merge risk "Minimal". Noted that the API has no authentication or per-user ownership checks anywhere, which existed before this PR. |

### PR 2 – Validation

Commits:
- [`02cc6fb`](https://github.com/Ezzgiturann/week6-habit-tracker/commit/02cc6fb7e0feeb761b6462801fd064f52fe3ca7e): agent output
- [`c5ea782`](https://github.com/Ezzgiturann/week6-habit-tracker/commit/c5ea7823cff74765b5952fec69ce49d3fe5c7a65): review fix: invisible names
- [`e34508a`](https://github.com/Ezzgiturann/week6-habit-tracker/commit/e34508af866d2385c8dd35c6686199d5fd29a21b): CodeRabbit fix

I reviewed this PR by running the app with `uvicorn` and sending `curl` requests.

| Review Finding | My Review | CodeRabbit Review |
|---|---|---|
| Empty habit names | `"   "` → 422 ✓. **But `"​"` (zero-width space) → 200, and it was stored.** `strip()` keeps format characters. **Fixed:** a name needs at least one visible character. 5 new test cases fail without the fix. | No comment. It reviewed the code after my fix, and its summary describes the rule ("rejects names without visible characters"). |
| Date format validation | `"2026-3-1"` → 422 ✓. The agent used `[0-9]` instead of `\d`, because `\d` also matches Arabic-Indic digits, and it ran the regex before `fromisoformat`. It avoided the same 3.11+ trap that CodeRabbit caught on PR #1. **However, errors come in two shapes:** a format error returns `detail` as a list, and a future date returns `detail` as a string. **Not fixed (known limit).** | No comment on the format check. It did not mention the two error shapes. |
| Invalid calendar dates | `2026-02-30` → 422, `2024-02-29` accepted, `2026-02-29` rejected. All are tested. ✓ | No comment. |
| Future dates | `2099-01-01` → 422 ✓. **But validation runs before the habit lookup**, so `POST /habits/99999/checkin` with a future day returns 422, not 404 "unknown habit". **Not fixed (known limit).** | No comment. It did not mention the 422-before-404 order. |
| Test coverage | Many edge cases are covered (tab and newline, 100/101 characters, leap days, a time part, a number instead of a string). **But the same database pollution as PR #1:** 0 → 28 habits after one `pytest` run. The agent's "database unchanged" assertions count rows in the real `habits.db`. I first left it as a known limit. After CodeRabbit rated it Major, I **fixed** it in [`e34508a`](https://github.com/Ezzgiturann/week6-habit-tracker/commit/e34508af866d2385c8dd35c6686199d5fd29a21b). | **1 actionable finding, rated Major (Data Integrity):** "Isolate database writes from the working `habits.db`." It quoted my PR description ("the reported increase from 0 to 28 habits confirms this behavior") and suggested a `tmp_path` fixture. This is the same issue I had left as a known limit. It rated it higher than I did. **I agreed and applied it** (173 → 173 habits before and after `./check.sh`). |
| Scope | My prompt said to change only `main.py` and `test_main.py`. **The agent deleted `habits.db` "without checking it first".** No data was lost (test data only), but it was an irreversible action I did not ask for. | Indirectly: its fix says "Do not delete the working database as cleanup." It did not comment on the agent deleting the file, which is not visible in the diff. |
| Cross-PR | Both PRs add `get_today()` and `DAY_PATTERN` to `main.py`, so whichever merges second will have a conflict. | No comment. It reviews one PR at a time. |

## 3. Comparing Human and AI Reviews

Bu çalışmada kendi yaptığım review ile CodeRabbit'in review'unu karşılaştırma fırsatım oldu. Streak PR'ında agent'ın yanlış bir iddiada bulunduğunu fark ettim ve kodun gerçekten nasıl çalıştığını kontrol ederek bu hatayı düzelttim. CodeRabbit ise benim yaptığım düzeltmede Python sürümüyle ilgili gözden kaçırdığım bir noktayı yakaladı. Bu durum, sadece agent'ın yazdığı kodun değil, benim yaptığım değişikliklerin de kontrol edilmesi gerektiğini gösterdi. Bence gereksinimleri anlayıp yanlış davranışı fark etmek benim için daha zordu. CodeRabbit ise teknik detayları ve olası uyumluluk sorunlarını bulma konusunda daha başarılıydı. İkisini birlikte kullanmanın daha iyi sonuç verdiğini düşünüyorum.

### Evidence from the PRs
- **CodeRabbit found the one bug I missed.** It was the Python 3.11+ `fromisoformat` behavior in PR #1. I could not have seen it by running tests locally on 3.9.
- **I found bugs CodeRabbit never saw, because I fixed them before it reviewed:**
  - the agent's false claim about `"2026-3-1"`
  - test database pollution
  - invisible names
- **Some of my findings needed a running app or the agent's own explanation**, not just the diff:
  - Comparing the agent's claim with what `fromisoformat` actually does.
  - Counting rows in `habits.db` before and after `pytest`.
  - Testing with `curl` against `uvicorn`.
- **CodeRabbit's suggestions came with a concrete test case.** For PR #1, its suggested regression input became a parametrized test.
- **CodeRabbit's hardening proposal (log volume) is a judgment call.** I did not apply it.
- **On PR #2, CodeRabbit's only finding was test database isolation.** I had already reported it in the PR description but left it unfixed. CodeRabbit cited my numbers and rated it Major. I then fixed it in `e34508a`.
- **Only my review caught these on PR #2:**
  - the invisible-name bug
  - the two error shapes
  - 422 before 404
  - the agent deleting `habits.db`
  - the merge conflict between the two PRs

## 4. What You Learned

Bu çalışmada prompt yazmanın düşündüğümden daha önemli olduğunu gördüm. İlk prompt'umda bazı detayları açıkça belirtmediğim için agent bazı konularda kendi kararını vermek zorunda kaldı. Özellikle streak hesaplamasında bugün check-in yapılmamışsa ne olması gerektiğini sonradan netleştirdim. Validation görevinde ise boş isimler, tarih formatı ve gelecek tarihler gibi durumları önceden belirttim. Böylece agent'ın ne yapmasını istediğimi daha iyi anlatabildim. Ayrıca kodun testlerden geçmesinin her zaman hatasız olduğu anlamına gelmediğini öğrendim. Yapılan değişiklikleri kendim kontrol etmek ve farklı durumlar için test yazmak gerekiyor. CodeRabbit'in de bazı önemli noktaları yakaladığını gördüm ancak her önerisinin doğru olduğunu varsaymamak gerektiğini anladım.

## 5. Conclusion

Genel olarak bu çalışma benim için AI agent kullanımı ve code review konusunda faydalı bir deneyim oldu. Sadece prompt yazıp kodu agent'a bırakmanın yeterli olmadığını gördüm. İstenen özellikleri doğru anlatmak, testleri kontrol etmek ve çıkan sonuçları incelemek de sürecin önemli bir parçası. Bundan sonraki projelerimde AI araçlarını kullanmaya devam ederim ancak ürettikleri kodu kontrol etmeden doğrudan kabul etmem. Bence AI araçları işleri kolaylaştırıyor ama son kararın ve kontrolün geliştiricide olması gerekiyor.
