# kobo2mail

Email every KoboToolbox respondent a nicely designed copy of their own submission, using **only a Kobo REST Service and GitHub Actions**. There is no server to host and nothing to install.

```
Kobo submission ──REST Service──► GitHub repository_dispatch ──► Actions run (~10 s) ──► SMTP ──► respondent
```

- The recipient address comes **from the submission itself** (the email question in your form).
- The **full submission** arrives in the REST payload. The form definition is never downloaded from Kobo.
- You choose which fields appear, with glob patterns. You can rename questions and translate choice codes into labels.
- The email is responsive HTML with a plain-text fallback. Group headers and repeat groups are rendered too.
- Mail goes through **Gmail** (with an app password) or **any SMTP** server.
- It uses only the Python standard library and the Python preinstalled on the runner.

## How it stays inside the free Actions quota

Billing rounds each job up to a whole minute, so the workflow keeps each submission to one short job:

| Measure | Effect |
|---|---|
| Single job, no `setup-python`, no `pip install` | Runs in about 10–15 s, which bills as 1 minute |
| Shallow sparse checkout (`kobo2mail/`, `templates/`, root files) | Checkout takes about 2 s |
| Job-level `if:` on `vars.EMAIL_FIELD` | A submission without an email address is **skipped**, and skipped jobs cost 0 minutes |
| `timeout-minutes: 2` | A stuck SMTP connection cannot burn minutes |
| No concurrency queue, artifacts or caches | Nothing extra to store or wait for |

Estimated cost:
- **Private repo:** 2,000 free minutes a month, which is about **2,000 emails a month**.
- **Public repo:** unlimited minutes, but see the privacy section below.

## Setup

### 1. Repository
- Fork or copy this repo. For production, use a **private** repository (see the privacy section).
- The workflow file must be on the default branch.

### 2. GitHub secrets and variables
Go to **Settings → Secrets and variables → Actions**.

| Secret | Required | Notes |
|---|---|---|
| `SMTP_USER` | yes | Gmail address or SMTP login |
| `SMTP_PASSWORD` | yes | A Gmail [app password](https://myaccount.google.com/apppasswords) (2-step verification required), or your SMTP password |
| `MAIL_FROM` | recommended | Sender address. Defaults to `SMTP_USER` |
| `SMTP_HOST` | smtp only | For example `smtp.office365.com` |
| `SMTP_PORT` | smtp only | `587` uses STARTTLS (the default) and `465` uses SSL |
| `MAIL_REPLY_TO` | optional | Where respondents' replies go |
| `MAIL_BCC` | optional | Receives a hidden archive copy of every email |

| Variable | Notes |
|---|---|
| `EMAIL_FIELD` | Same path as `email_field` in the config, for example `contact/email`. It turns on the free skip check. |
| `MAIL_PROVIDER` | `gmail` or `smtp`. It overrides `provider` in `config.json`. |

### 3. GitHub token for Kobo
Create a **fine-grained personal access token**:
- **Repository access:** only this repository.
- **Permissions:** *Contents → Read and write*. This is what `repository_dispatch` requires.

### 4. Kobo REST Service
In Kobo, open your project → **Settings → REST Services → Register a new service**.

| Field | Value |
|---|---|
| Endpoint URL | `https://api.github.com/repos/OWNER/REPO/dispatches` |
| Type | JSON |
| Custom HTTP headers | `Authorization` = `Bearer <your token>`<br>`Accept` = `application/vnd.github+json` |
| Custom wrapper around JSON submission | `{"event_type":"kobo_submission","client_payload":{"submission":%SUBMISSION%}}` |
| Select fields subset | Optional. Sending fewer fields means smaller payloads and less personal data in GitHub. |

- **Nest the submission.** It must sit under `submission`, because GitHub allows at most 10 top-level keys in `client_payload`.
- **Success.** Kobo shows **HTTP 204** when GitHub accepted the event.
- **Next step.** Check the run in the repo's **Actions** tab.

## Configuration (`config.json`)

The config is committed to the repo and contains no secrets.
- Settings are resolved in this order: built-in defaults, then `forms.default`, then `forms.<asset UID>`.
- The asset UID is the `_xform_id_string` of the submission, the same ID as in the Kobo project URL. One repo can therefore serve several forms.
- See [config.example.json](config.example.json).

| Key | Meaning |
|---|---|
| `email_field` | Path of the question holding the respondent's email. If empty, the first field named `*email` / `*e_mail` that contains an address is used. |
| `subject`, `title`, `intro`, `footer` | Text that can use `$placeholders` (see below) |
| `from_name` | Display name of the sender |
| `brand_color`, `logo_url` | Header color, plus an optional logo (an absolute https URL) |
| `include` / `exclude` | Glob patterns on the full Kobo path, such as `contact/*`, `_*` or `meta/*`. A field is shown if it matches `include` and does not match `exclude`. **Exclude always wins.** If a repeat group is included, its child fields are included as well. |
| `labels` | Display names, keyed by full path (`contact/phone`) or by bare name (`phone`). Also used for group and repeat headers. Unlabelled fields are humanized: `phone_number` becomes "Phone number". |
| `value_labels` | Choice labels: `{"gender": {"f": "Female"}}`. Space-separated values from select_multiple are split and mapped. |
| `hide_empty` | Skip unanswered questions (default `true`) |
| `group_headers` | Show a section header for each Kobo group (default `true`) |
| `ungrouped_label` | Header for questions outside a group that come after a group (default "Other answers") |
| `template` | Path to the HTML template (default `templates/default.html`) |

### Placeholders
Every simple field is available as a placeholder in `subject`, `title`, `intro`, `footer` and the template:
- By its full path, with `/` replaced by `__`: `contact/name` becomes `$contact__name`.
- By its bare name, `$name`, when that name is unique in the submission.
- Choice values are already mapped through `value_labels`.

Extra placeholders:
- `$submission_id` and `$submitted_at`
- In the template only: `$answers_table`, `$logo_block` and `$brand_color`

Rules:
- Unknown placeholders render as empty text.
- In a template, write `$$` to get a literal `$`.

### Custom design
Copy [templates/default.html](templates/default.html), change it, and point `template` at your copy. Use inline styles, because email clients ignore most `<style>` blocks.

## Local testing

```bash
python -m unittest discover -s tests -v
python -m kobo2mail --submission examples/sample_submission.json --preview preview.html   # open in a browser
python -m kobo2mail --submission examples/sample_submission.json --dry-run               # print, don't send
```

To send a real email:
1. Put your own address in a copy of the sample file.
2. Set `SMTP_USER`, `SMTP_PASSWORD` and `MAIL_FROM` in your environment.
3. Run the command without `--dry-run`.

On GitHub, **Actions → Send submission email → Run workflow** gives you two inputs:
- **Submission JSON:** paste one, or leave it empty to use the sample.
- **`dry_run`:** untick it to really send.

## Privacy

- **Logs.** The script never prints submission values. The recipient address is masked in the logs, and errors name fields, not values. Only `--dry-run` prints the email, and it is meant for manual tests.
- **Event payloads.** GitHub keeps the dispatch payload with each run.
  - In a **public** repo, anyone can open the run logs.
  - Keep public repos for sharing the code only. **Run production from a private repo**, and delete old runs if your data policy requires it.
- **Kobo field subset.** Selecting only the fields you need in the REST Service limits what reaches GitHub.

## Limits
- **Attachments.** Photos and files are not attached. Their Kobo URLs require authentication.
- **Gmail quota.** Gmail allows about 500 recipients a day. Use an SMTP relay for more.
- **Failed runs.** HTTP 204 only means GitHub accepted the event. If sending then fails, the run fails and Kobo does **not** retry. Check the Actions tab or enable failure notifications.

## License
MIT
