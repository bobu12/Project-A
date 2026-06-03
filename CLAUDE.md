# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is an **AWS solution-architecture assignment**, not a conventional application
codebase. It is a collection of deliverables — CloudFormation templates, Python
scripts, a PHP web application, a database dump, architecture diagrams, and the
assignment brief — that together describe and implement a single system.

There is **no build system, package manifest, test suite, or CI**. Files are
standalone artifacts. Don't look for `make`, `npm`, `pytest`, etc. — they don't
exist here. "Running" something means deploying a CloudFormation stack, invoking a
Lambda, or hosting the PHP app on a web server backed by RDS.

## The system being built (the big picture)

A video/media web portal hosted on AWS:

1. A **PHP web app** (in `PhpProject1.zip`) runs on a web server (EC2). Users log
   in and submit "products" with a photo, thumbnail, and video.
2. Uploaded media lands in an **S3 bucket**.
3. A **Lambda function** generates a thumbnail from the uploaded media.
4. Another process **validates uploaded videos** by checking file extensions
   (only `.mp4` / `.3gp` are considered valid videos).
5. Persistence is a **MySQL RDS instance with a read replica** (later iterations
   use an Aurora `RDS::DBCluster`) for high availability and auto-scaling.

The architecture diagrams (`Initial Analysis.jpeg`, `Initial Challenges.jpeg`,
`Analysis of final Design.jpeg`, `Question 1 Architecture with AWS MYSQL RDS.png`,
`template1-designer.png`) trace the design evolution. `Assignment Document.docx`
is the original brief.

## Map of the artifacts

### Infrastructure (CloudFormation, JSON)

These build on each other — read them in order to follow the design's evolution:

- `Q1Cloudformation_Attempt1.json` — earliest, smallest attempt.
- `CloudFormationTemplateQ1` — RDS DBInstance + read replica, VPC, security
  groups, IAM user. (No `.json` extension, but it is JSON.)
- `FinalRDS_Template.json` — the most complete stack: VPC + IGW, Aurora
  `RDS::DBCluster` with two `DBInstance`s, S3 bucket + policy, CloudFront origin
  access identity, Lambda function, Route53 record, CloudWatch alarms +
  dashboard, SNS topic, IAM user/access key. Treat this as the current
  source-of-truth architecture.

Templates contain `AWS::CloudFormation::Designer` metadata — these are
visual-designer coordinates, not functional resources; ignore them when reasoning
about the stack.

### Lambda / scripts (Python)

- `Question4_PythonScript_Approach1.py` — the **video authenticity check**. Lists
  S3 objects via boto3 and flags any key whose extension is not `.3gp`, `.mp4`,
  or `.png` (i.e., incorrectly uploaded files).
- `Question4_PythonScript_Approach2_Using_Lamda_Function.py` — the **thumbnail
  Lambda**. S3-triggered (`event['Records'][0]['s3']`), downloads the object to
  `/tmp`, resizes with PIL, optimizes with bundled mozjpeg (`bin/cjpeg`), and
  re-uploads with an `image-processed: true` metadata flag to prevent reprocessing
  loops. It imports a `config` module (max_width/height, output_bucket, prefix,
  etc.) that is **not present in the repo** — it must be supplied in the Lambda
  deployment package.

### Web application (`PhpProject1.zip`)

A small PHP app (PHP ~7, `mysqli`). Unzip to inspect:

```bash
unzip -l PhpProject1.zip          # list contents
unzip PhpProject1.zip -d /tmp/php # extract for editing
```

Structure inside the zip (`PhpProject1/`):
- `connection.php` — central DB access layer (`mysqli_con_info`, `executeInsert`,
  `executeQuery`) **with hardcoded RDS endpoint and credentials**. All other PHP
  files `include_once 'connection.php'`.
- `index.php` / `logInProc.php` / `logout.php` — session-based login flow against
  the `login` table.
- `dashboard.php` — post-login UI.
- `productEntry.php` — handles photo/thumbnail/video uploads. Validates
  extensions, then stores file bytes as **BLOBs in the `product_details` table**
  (not on disk — files are read with `file_get_contents` then `unlink`ed).
- `uploads/` — transient working directory for `move_uploaded_file`.

### Database

- `phpproject1.sql` (~3.8 MB) — full MySQL dump (also duplicated inside the zip).
  Loads the `login` and `product_details` schema plus data. Import with:
  `mysql -h <rds-endpoint> -u <user> -p innodb < phpproject1.sql`

## Conventions and constraints to respect

- **Allowed media extensions are the contract** across the whole system: videos
  `.3gp` / `.mp4` (also `.mpeg` / `.mpg` accepted in PHP), images
  `.jpg/.jpeg/.png/.bmp/.gif`. The S3 validation script and PHP upload handler
  must stay in agreement on this list.
- The thumbnail Lambda relies on the `image-processed` S3 metadata flag as an
  idempotency guard — preserve that pattern if you modify it.
- CloudFormation parameters carry `NoEcho: true` on credentials; keep secrets out
  of `Default`/`Description` fields.
- This is legacy assignment code: it contains hardcoded credentials, SQL built via
  string interpolation in `logInProc.php`, and plaintext password comparison. If
  asked to extend or modernize it, call these out rather than copying the pattern.

## Working in this repo

- The default development branch for this environment is
  `claude/claude-md-docs-Nido6`. Commit and push there.
- Binary artifacts (`.jpeg`, `.png`, `.docx`, `.xlsx`, `.zip`) are committed
  directly; there is no asset pipeline.
