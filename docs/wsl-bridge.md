# WSL access to Windows PaperFlow

PaperFlow, Zotero, and Obsidian stay on Windows. WSL Codex opens the **same**
Vault through `/mnt/<drive>/...` and calls the Windows PaperFlow executable
through [`tools/paperflow-wsl`](../tools/paperflow-wsl). There is no WSL Python
installation, second Vault, or second skill installation.

## One-time WSL command

First complete `setup-windows.ps1` in PowerShell. In WSL, link the launcher into
your command path (substitute the actual Windows drive and clone location):

```bash
mkdir -p ~/.local/bin
ln -s /mnt/e/projects/research-stack/PaperFlow/tools/paperflow-wsl ~/.local/bin/paperflow
export PATH="$HOME/.local/bin:$PATH"
```

Put the `export PATH=...` line in your shell startup file if needed. The symlink
points to a launcher only; it does not copy a skill or Vault. `paperflow init`
should normally be run on Windows, where Obsidian and Zotero are configured.

## Use

```bash
cd '/mnt/e/Obsidian/Research'
paperflow sync
paperflow doctor
codex
```

Codex sees the Vault's existing `.agents/skills/paperflow` at this location.
The repository's `.agents/skills/paperflow` is the maintained skill source;
Windows `paperflow init` installs it into the Vault. WSL reads that same Vault
directory. Do not install or copy the skill into a separate WSL home directory.

The launcher looks for `.paperflow/config.toml` in the current directory or its
parents and passes that Vault to Windows PaperFlow. Outside a Vault, Windows
PaperFlow uses its existing active Vault pointer. You can override either with
`--vault` in WSL or Windows form:

```bash
paperflow process vaswani2017attention --vault '/mnt/e/Obsidian/Research'
paperflow doctor --vault 'E:\Obsidian\Research'
```

Relative WSL Vault paths work too, including spaces and Unicode names. `init`
also translates its positional Vault path. Paths on the Linux-only WSL filesystem
are rejected as Vault targets so that the launcher cannot create a second Vault
there. Other arguments, including citekeys and section IDs, pass through
unchanged. The Windows CLI may print Windows paths; the corresponding WSL path
can be obtained with `wslpath -u 'E:\path\from\output'` when opening an artifact
from WSL.

If the launcher reports a missing executable, run Windows setup again and verify
that this checkout contains `.venv/Scripts/paperflow.exe`. The bridge returns the
Windows CLI's exit code, so errors from `sync`, `ingest`, `process`, and `doctor`
remain visible to Codex.

## Verification

On Windows with WSL installed, `python -m pytest tests/test_wsl_bridge.py` tests
path conversion, Vault discovery, Windows path passthrough, the Linux-only path
guard, and exit-code propagation using a stub executable. `python -m pytest`
also runs the native Windows CLI tests.
