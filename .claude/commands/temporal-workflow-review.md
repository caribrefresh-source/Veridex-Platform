# temporal-workflow-review

Review Temporal workflow definitions for correctness — idempotency, retries, compensation.

## Provide
Workflow name or code file path to review. This skill reviews design quality, not runtime state (use temporal-worker-health for runtime).

## Review Checklist

### 1. Idempotency
- Does every workflow activity use a deterministic idempotency key?
- Are workflow IDs derived from business identifiers (e.g., document ID), not random UUIDs?
- If re-run with same input, does it produce the same output without side effects?

### 2. Retry Policies
Check every Activity definition has explicit retry policy:
```
RetryPolicy{
  InitialInterval:    1 second
  MaxInterval:        30 seconds  
  BackoffCoefficient: 2.0
  MaxAttempts:        5           # Not infinite unless justified
  NonRetryableErrors: [...]       # Business errors that should not retry
}
```
Flag: `MaxAttempts: 0` (infinite) without justification.
Flag: Missing `NonRetryableErrors` for validation/auth failures.

### 3. Workflow Timeouts
- `WorkflowExecutionTimeout`: Set? Not unlimited?
- `WorkflowRunTimeout`: Shorter than execution timeout?
- `ActivityScheduleToCloseTimeout`: Set per activity?
Flag: Missing timeouts → workflow runs forever if worker dies.

### 4. Compensation / Saga Pattern
For multi-step workflows (ingest → process → store → index):
- Is there a compensation path for partial failures?
- Are compensation activities also idempotent?
- Is rollback order reverse of forward order?

### 5. Signal Handling
- Are Signal handlers idempotent?
- Is there a deduplication mechanism for signals?

### 6. Query Handlers
- Do Query handlers only read state (no side effects)?

### 7. Versioning (for existing workflows)
- Are workflow code changes backwards-compatible?
- Is `workflow.GetVersion()` used for branching logic changes?
- Are old workflow history replays tested?

### 8. Determinism Violations
Flag: Any non-deterministic code in workflow function:
- `time.Now()` → use `workflow.Now(ctx)`
- `rand.Intn()` → use `workflow.SideEffect()`
- Goroutines → use `workflow.Go()`
- `os.Getenv()` → pass via activity input

## Report
Checklist result per category. High/Medium/Low severity findings with specific line references.
