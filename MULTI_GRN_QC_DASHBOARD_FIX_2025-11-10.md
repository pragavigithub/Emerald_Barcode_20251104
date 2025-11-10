# Multi GRN QC Dashboard Fix - November 10, 2025

## Issue Summary
**Error:** `jinja2.exceptions.UndefinedError: 'str object' has no attribute 'strftime'`

**Location:** `templates/qc_dashboard.html` (line 550)

**Root Cause:** The template was attempting to call `.strftime()` on `batch.qc_reviewed_at`, but this field was sometimes stored as a string instead of a datetime object. The `.strftime()` method only works on datetime objects, not strings.

## Error Details

```
File "templates/qc_dashboard.html", line 550
<small>{{ batch.qc_reviewed_at.strftime('%Y-%m-%d %H:%M') if batch.qc_reviewed_at else 'N/A' }}</small>
```

The template assumed `qc_reviewed_at` was always a datetime object, but in some cases it was stored as a string (possibly due to serialization/deserialization or database type inconsistencies).

## Fix Applied

### Template Changes
**File:** `templates/qc_dashboard.html` (line 552-564)

**Before:**
```jinja2
<small>{{ batch.qc_reviewed_at.strftime('%Y-%m-%d %H:%M') if batch.qc_reviewed_at else 'N/A' }}</small>
```

**After:**
```jinja2
<small>
    {% if batch.qc_reviewed_at %}
        {% if batch.qc_reviewed_at is string %}
            {{ batch.qc_reviewed_at }}
        {% else %}
            {{ batch.qc_reviewed_at.strftime('%Y-%m-%d %H:%M') }}
        {% endif %}
    {% else %}
        N/A
    {% endif %}
</small>
```

**How it works:**
1. First checks if `qc_reviewed_at` exists
2. Then checks if it's a string type
3. If string: displays it as-is
4. If datetime: formats it using strftime
5. If null/None: displays "N/A"

## Consistency Check

This fix is **consistent** with existing patterns in the same template:

- **Line 108:** GRPO updated_at handling
  ```jinja2
  {{ grpo.updated_at.strftime('%Y-%m-%d %H:%M') if grpo.updated_at and grpo.updated_at is not string else (grpo.updated_at if grpo.updated_at else 'N/A') }}
  ```

- **Line 186:** Transfer updated_at handling
  ```jinja2
  {{ transfer.updated_at.strftime('%Y-%m-%d %H:%M') if transfer.updated_at and transfer.updated_at is not string else (transfer.updated_at if transfer.updated_at else 'N/A') }}
  ```

- **Line 452:** Multi GRN batch submitted_at handling
  ```jinja2
  {{ batch.submitted_at.strftime('%Y-%m-%d %H:%M') if batch.submitted_at is not string else batch.submitted_at }}
  ```

All datetime fields in the QC dashboard now use the same defensive programming pattern.

## Database Schema

### MultiGRNBatch Model (modules/multi_grn_creation/models.py)

```python
qc_reviewed_at = db.Column(db.DateTime, nullable=True)
```

The model correctly defines `qc_reviewed_at` as a `DateTime` column. The string issue likely occurs due to:

1. **SQLite mode:** Replit is currently running in SQLite mode (MySQL connection not configured)
2. **Data migrations:** Some records might have been migrated with string values
3. **Serialization:** JSON serialization/deserialization can convert datetime to strings

### MySQL Migration Status

No database changes needed. The field is correctly defined in:
- `migrations/mysql_multi_grn_consolidated.sql`
- `migrations/mysql/changes/2025-11-09_multi_grn_qc_workflow_and_labels.sql`

The fix is purely defensive template handling to work with both SQLite and MySQL, and to handle any edge cases where datetime fields might be serialized as strings.

## Testing Results

✅ Application restarted successfully  
✅ Template renders without errors  
✅ QC Dashboard can handle both datetime and string types  
✅ Consistent with other datetime field handling in the same template  

## Related Issues Fixed

This is the **second Multi GRN issue fixed today**:

1. **Step 3 Template Fix** - Removed `grpo_doc` undefined error (see `MULTI_GRN_STEP3_TEMPLATE_FIX_2025-11-10.md`)
2. **QC Dashboard Fix** - Fixed `qc_reviewed_at` datetime/string handling (this document)

## Recommendations

### For Production Deployment

When deploying to production with MySQL:

1. Ensure all datetime fields are properly typed in MySQL
2. Run database integrity check to convert any string datetime values to proper DATETIME
3. Consider adding a migration script to clean up any string datetime values:

```python
# Example cleanup script (if needed)
from modules.multi_grn_creation.models import MultiGRNBatch
from datetime import datetime

batches = MultiGRNBatch.query.all()
for batch in batches:
    if isinstance(batch.qc_reviewed_at, str):
        try:
            batch.qc_reviewed_at = datetime.strptime(batch.qc_reviewed_at, '%Y-%m-%d %H:%M:%S')
        except:
            batch.qc_reviewed_at = None
db.session.commit()
```

### For Future Development

When working with datetime fields in templates:
1. Always check if the value is a string before calling strftime
2. Use the pattern established in this template for consistency
3. Consider creating a Jinja2 custom filter for datetime formatting to centralize this logic

## Files Modified
- `templates/qc_dashboard.html` (line 552-564)

## Related Documentation
- `MULTI_GRN_STEP3_TEMPLATE_FIX_2025-11-10.md`
- `QC_APPROVAL_IMPLEMENTATION_SUMMARY.md`
- `MULTI_GRN_JSON_FIX_AND_MYSQL_MIGRATION.md`
