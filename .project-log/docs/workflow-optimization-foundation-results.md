# Foundation and prototype validation checkpoint

Date: 2026-09-20. This is an intermediate record, not release acceptance.

## Scope and isolation

Source: D:/Project/vibe-coding. Every test, fixture, copied source snapshot, temporary profile, isolated Python installation and report is under D:/Project/vibe-coding-validation. The actual paper project and installed global profile were not modified. No commit or push occurred.

TASK-014's contract is frozen. TASK-015's Git binding repair and TASK-016's bounded entry/bootstrap fixes have independent acceptance. TASK-017/018 have passed the listed experimental checks, with TASK-019 as a separate production go/no-go gate. TASK-020 onwards are not implemented. No Project Goal success condition is claimed complete from these foundation checks alone.

## Git binding

- pre-fix-015 reproduced the original failures: eight binding tests, three failures and three errors.
- Fixed implementation passes Windows and Linux baseline and eight targeted binding checks. Baseline executes 41 tests with one existing skip, not 41 passing tests plus a skip.
- Independent reviewer-015 first found corrupt branch references misclassified as unborn. Its failed REPORT.md and old snapshots are retained.
- reviewer-015/REPORT-v2.md accepts the repaired inspected scope with 28 passing independent checks, including the old implementation as a negative control.
- Accepted loop_state.py SHA-256: 4cb6fd9833c22e606a177dadcdd5d318a2e247cf7196cc21b0144c46ddcb8019.

## Platform entry

- Windows PowerShell 5.1, configured Python 3.11.15: launcher-016-v13 passes all 13 entry checks, baseline 41 with one skip, and eight binding checks. PowerShell 7 is not installed and has not been verified.
- Linux WSL Ubuntu, isolated Python 3.11.16: linux-016-v4 passes all six Unix entry checks and package/project validation. Its baseline and Git checks previously passed in linux-016-v2.
- Initial Linux failures were genuine CRLF defects. A one-line replacement normalized only one line; full-file LF normalization plus .gitattributes fixed the scripts. Both failed runs are retained.
- Independent reviewer-016/REPORT-v2.md found additional PS5 empty/quoted-argument loss and inconsistent BOM/relative/multiline bootstrap parsing. These were not covered by the initial smoke checks and were not dismissed.
- Repairs use a shared native argv transport and consistent configured-path parsing. Follow-up main tests found lost stdout, then a leaked .NET VoidTaskResult contaminating the captured interpreter path. Each failing run is retained; the latter was directly reproduced as a two-element return value and corrected with an explicit void discard.
- A further inherited GBK-output regression was reproduced and fixed with explicit UTF-8 child IO. Exact argument and simultaneous 100KB stderr forwarding checks pass. PowerShell EncodedCommand startup CLIXML was isolated as a harness-host issue using a file-based driver; product stderr bytes were not discarded to make the check pass.
- Final independent reviewer-016/REPORT-v3.md accepts the current UTF8 source: Windows 42 passing methods plus one platform skip; Linux 41 passing methods plus two platform skips. The earlier pre-UTF8 report is retained separately, as are all failed runs. O016-01 remains an explicitly excluded policy decision (Q-001), not a successful assertion.

## Transaction and exchange prototypes

All implementation here remains in the external prototype directory, not integrated into the runtime.

Windows and Linux prototype/runs/*-018-v2 each pass 32 state tests and 12 real Git exchange tests. Checks cover begin/block/resume/finish, independent work while another task waits, cancellation, no historical Goal fallback, command receipts, stale revision, concurrent writers, hard termination before/after commit, projection repair, unknown fields, two clones, divergence, branch A/B/A, linked worktrees, malformed/missing snapshot payloads and interrupted manifest publication.

The SQLite and atomic-JSON experiments deliberately share a reducer and currently serialize a whole state document. Both survive exercised process termination; this does not test power loss, filesystem corruption, network shares or all concurrent external Git operations. SQLite's transaction mechanism alone does not prove the future application schema or importer safe.

Benchmarks use synthetic 38/500/2000-task states and 20 accepted writes per case. Raw reports and source/harness hashes are in each run. Earlier windows-017-v2 median writes were 7.233/9.198/15.128 ms for SQLite and 3.205/4.809/10.123 ms for JSON. These numbers describe that version and environment only; later invariant checks have separate results. Linux uses /mnt/d and must not be represented as a native ext4 performance test. No evidence here establishes that SQLite is faster. Production backend choice must account for query cost, transaction requirements, snapshot volume and maintenance complexity at G1.

## Independent gates and next boundary

### Current checkpoint after repaired-version review

Final PS5/7 independent follow-up: reviewer-016/followup-ps7-v4-20260920-205756/REPORT-v4.md passes seven decisive methods with both hosts. All six scoped source hashes match before and after; previous REPORT-v3 and acceptance hashes are preserved. This adds current argument-boundary coverage without claiming every former baseline method was rerun on PS7. No test or actual user environment was installed into the source tree.

reviewer-g1/REPORT-v2.md and results-v2.json retain the original NO-GO and independently confirm both old failures as negative controls, then pass eight repaired-version case groups. Windows and Linux main suites each pass 32 state tests and 19 exchange tests on the repaired hashes. TASK-017/018 are accepted as experiments, not production integration. G1 permits the next bounded design step only; TASK-019 awaits user Q-002 on adopting the cooperative Git lock and manual crash-recovery cost. TASK-020.md and ARCH-001 are draft proposals, not shipped interfaces.

Portable PowerShell 7.4.6 was downloaded under the external validation directory and verified against the publisher checksum list; no system install or PATH change. It exposed a host -File argument transformation: equals-form drive paths are split before the script. The exact PS5/7 control is ps7-argv-probe-results.json. Latest source explicitly rejects the ambiguous pattern and documents split option/value usage. Proper script-to-script array splatting preserves equals-form arguments; an initial test-driver array-literal mistake is preserved as a harness failure, not a product defect. Main powershell7-016-v3 and ps5-016-v15 each pass 16 entry tests. Latest PS-specific patch is separately independently reviewed rather than relabeling older source hashes.

### G1 first review and remediation

reviewer-g1/REPORT.md records NO-GO from two independently executed Windows adversarial reproductions. F01 captures an A store, switches to branch B, then wrongly publishes A-only state and acknowledges A as exported. F02 imports a correctly hashed but semantically malformed receipt and returns that unrelated receipt when retrying the original command. Hash validity alone is insufficient. The original report, snapshots, observations and failed harness setup are retained.

The external prototype now binds project/worktree/branch/store context while holding an exclusively owned Git index lock, checks the binding during normal and recovery publication, and never removes a foreign lock. This coordinates ordinary Git checkout/switch, not arbitrary plumbing or forced .git edits. Hard termination may leave a stale lock requiring explicit investigation; automatic stale-lock removal is not implemented. The experimental boundary is documented in prototype/EXPERIMENT.md.

Receipt fixes validate object structure, canonical command/action/payload identity, event/receipt headers and immutable shared historical records on import. Historical receipt revisions are not treated as global clocks. Windows windows-g1fix-v1 passes 32 state checks and 19 exchange checks, including new negative cases. Linux and independent repaired-version review are pending. TASK-017/018 were reopened as implemented-unverified; G1 remains NO-GO until independently resolved, not silently promoted by main-agent tests.

Reviewer 01a0ba37-f020-7670-be65-6e850e1ae325 handles TASK-016. Reviewer 01a0bc3e-c68f-7b11-96d7-7b1c19d076ed independently examines the transaction/exchange prototype and G1 recommendation. Both have read-only product/prototype scope and external-only test/report write scopes.

G1 is pending. Do not integrate the experimental store, migrate .project-log, change the actual installation, or claim the full optimized framework is delivered before the relevant gates. TASK-027 still requires explicit target-specific approval.
