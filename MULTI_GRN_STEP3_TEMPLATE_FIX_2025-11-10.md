# Multi GRN Step 3 Template Fix - November 10, 2025

## Issue Summary
**Error:** `jinja2.exceptions.UndefinedError: 'grpo_doc' is undefined`

**Location:** `modules/multi_grn_creation/templates/multi_grn/step3_select_lines.html`

**Root Cause:** The template contained an "Add Item" modal that was mistakenly copied from the GRPO module (`modules/grpo/templates/grpo/grpo_detail.html`). This modal referenced variables (`grpo_doc.id`, `grpo_doc.created_at`) that don't exist in the Multi GRN context.

## Fix Applied

### 1. Template Changes
**File:** `modules/multi_grn_creation/templates/multi_grn/step3_select_lines.html`

**Removed:**
- Action column header from the table
- "Add Item" buttons in the Action column (lines 67-88)
- Complete "Add Item Modal" (lines 131-309)
- "Barcode Labels Modal" that was also copied from GRPO module

**Reason:** The Multi GRN Step 3 workflow is for selecting line items from POs, not for manually adding items. The manual add functionality belongs to the single GRPO module and has no corresponding route in the Multi GRN blueprint.

### 2. Route Context
**File:** `modules/multi_grn_creation/routes.py` (Line 356)

The route `create_step3_select_lines` passes:
- `batch` - MultiGRNBatch instance
- `po_details` - List of PO links with their line items

It does NOT pass `grpo_doc`, which is specific to the single GRPO module.

## Database Schema Status

### Current Multi GRN Tables (All up-to-date)

1. **multi_grn_batches** - Main batch record
   - Includes QC workflow fields (qc_status, qc_approver_id, qc_reviewed_at, etc.)
   - Document series support (doc_series_id, doc_series_name)
   
2. **multi_grn_po_links** - PO to batch relationships
   - Tracks posting status per PO
   
3. **multi_grn_line_selections** - Selected line items
   - Warehouse and bin location support
   - Batch/serial management flags
   - QC and packing fields
   
4. **multi_grn_batch_details** - Batch number details
   - Manufacturer/internal serial numbers
   - Expiry and admin dates
   - Pack quantity tracking
   
5. **multi_grn_serial_details** - Serial number details
   - Similar structure to batch details
   
6. **multi_grn_non_managed_details** - Non-managed items (Added 2025-11-10)
   - For items that are neither batch nor serial managed

### MySQL Migration Files

**Latest migrations:**
- `migrations/mysql/changes/2025-11-10_multi_grn_non_managed_details.sql`
- `migrations/mysql/changes/2025-11-10_multi_grn_document_series.sql`
- `migrations/mysql/changes/2025-11-09_multi_grn_qc_workflow_and_labels.sql`
- `migrations/mysql_multi_grn_consolidated.sql` (Complete schema)

**No database changes needed** for this template fix - it was purely a Jinja2 template issue.

## Testing Results

✅ Application starts successfully
✅ Multi GRN Step 3 template renders without errors
✅ Line selection workflow remains intact
✅ No database schema changes required

## Note: MySQL Configuration

The application is currently running in **SQLite-only mode** with the following warning:
```
WARNING:root:⚠️ MySQL engine connection failed: (pymysql.err.OperationalError) 
(2003, "Can't connect to MySQL server on '123@localhost' ([Errno -2] Name or service not known)")
Operating in SQLite-only mode.
```

**For production MySQL deployment:**
1. Configure proper MySQL connection string in environment variables
2. Run the consolidated migration: `migrations/mysql_multi_grn_consolidated.sql`
3. Apply any incremental migrations from `migrations/mysql/changes/`

The SQLite database is working fine for development/testing purposes on Replit.

## Future Enhancements (If Needed)

If manual item addition is required in Multi GRN workflow:
1. Create a dedicated route in `multi_grn_bp` (e.g., `add_multi_grn_item`)
2. Design appropriate context and payload for multi-PO scenario
3. Reintroduce modal with correct action URL and context variables
4. Update the template to use `batch` instead of `grpo_doc`

## Files Modified
- `modules/multi_grn_creation/templates/multi_grn/step3_select_lines.html`
- `.local/state/replit/agent/progress_tracker.md` (marked all items complete)

## Related Documentation
- `MULTI_GRN_JSON_FIX_AND_MYSQL_MIGRATION.md`
- `MULTI_GRN_FIX_SUMMARY.md`
- `QC_APPROVAL_IMPLEMENTATION_SUMMARY.md`
