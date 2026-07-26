# GetGithubReleases

Generate Markdown release note files from closed GitHub issues in a specific milestone.

The script reads closed issues from one repository at a time, filters by milestone name, and groups issue links into:
- Enhancements (`enhancement` label)
- Bug Fixes (`bug` label)

It then writes a `<milestone>.md` file into a local `Releases` folder for each configured mod target.

## Script

- `getGithubReleases.py`

## Requirements

- Python 3.8+
- Packages:
  - `PyGithub`
  - `colorama`

Install dependencies:

```powershell
pip install PyGithub colorama
```

## Configuration

Create `config.json` in the same folder as the script with your GitHub personal access token:

```json
{
  "ACCESS_KEY": "your-access-token"
}
```

Token notes:
- A classic PAT with `repo` read access is typically enough for private repos.
- Public repos usually require minimal read permissions.

## How It Works

For each `process_release(...)` call in `__main__`:

1. Builds milestone name as:
   - `<mod_name> <release_date>`
2. Queries closed issues in the target repo.
3. Keeps only issues whose milestone title matches exactly.
4. Adds issue links to sections based on labels:
   - `enhancement`
   - `bug`
5. Writes output to:
   - `<github_folder>Releases\<milestone>.md`

## Output Format

Each generated file includes:

- A title linking to the matching GitHub milestone
- `Enhancements` section
- `Bug Fixes` section

Example output file name:

- `FamilyTies 2023-02-26.md`

## Usage

From this folder, run:

```powershell
python .\getGithubReleases.py
```

The script currently uses hardcoded values in `__main__` for:
- `github_account`
- `github_root_folder`
- `release_date`
- The full list of `process_release(...)` targets

## Customizing

To use this script for a different account/project set, edit these values in `getGithubReleases.py`:

- `github_account`
- `github_root_folder`
- `release_date`
- `process_release(...)` calls

Parameter meaning for:

```python
process_release(github_api, github_account, github_root_folder, github_repo, mod_path, mod_name, release_date)
```

- `github_repo`: Repository name under `github_account`
- `mod_path`: Optional subfolder path segment (for example `LE\\` or `SE\\`), or empty string
- `mod_name`: Mod/project name; also part of milestone title
- `release_date`: Date suffix used in milestone title

Milestone title must match exactly:

- `<mod_name> <release_date>`

## Important Behavior and Limitations

- Issues without a milestone are ignored.
- Issues with labels other than `enhancement` and `bug` are ignored.
- If an issue has both labels, it may appear in both sections.
- If no matching milestone is found among closed issues, no file is written.
- The script uses Windows-style paths.

## Troubleshooting

- `ModuleNotFoundError`:
  - Install required packages with `pip install PyGithub colorama`
- `FileNotFoundError: config.json`:
  - Ensure `config.json` exists in the script folder
- Empty release notes:
  - Verify milestone title matches exactly
  - Verify target issues are closed
  - Verify labels are `enhancement` or `bug`
- Authentication errors:
  - Verify token validity and permissions
