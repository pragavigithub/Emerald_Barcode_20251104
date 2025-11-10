"""
Multiple GRN Creation Routes
Multi-step workflow for creating GRNs from multiple Purchase Orders
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from modules.multi_grn_creation.models import (MultiGRNBatch, MultiGRNPOLink, MultiGRNLineSelection,
                                                MultiGRNBatchDetails, MultiGRNSerialDetails, MultiGRNNonManagedDetail)
from modules.multi_grn_creation.services import SAPMultiGRNService
import logging
from datetime import datetime, date
import json
from decimal import Decimal, InvalidOperation

multi_grn_bp = Blueprint('multi_grn', __name__, 
                              template_folder='templates',
                              url_prefix='/multi-grn')

@multi_grn_bp.route('/')
@login_required
def index():
    """Main page - list all GRN batches with filtering, search and pagination"""
    if not current_user.has_permission('multiple_grn'):
        flash('Access denied - Multiple GRN permissions required', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search_term = request.args.get('search', '').strip()
        from_date_str = request.args.get('from_date', '').strip()
        to_date_str = request.args.get('to_date', '').strip()
        status_filter = request.args.get('status', '').strip()
        
        query = MultiGRNBatch.query.filter_by(user_id=current_user.id)
        
        if search_term:
            search_pattern = f'%{search_term}%'
            query = query.filter(
                db.or_(
                    MultiGRNBatch.batch_number.ilike(search_pattern),
                    MultiGRNBatch.customer_name.ilike(search_pattern),
                    MultiGRNBatch.customer_code.ilike(search_pattern),
                    MultiGRNBatch.id.cast(db.String).ilike(search_pattern)
                )
            )
        
        if status_filter:
            query = query.filter(MultiGRNBatch.status == status_filter)
        
        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
                query = query.filter(MultiGRNBatch.created_at >= from_date)
            except ValueError:
                logging.warning(f"Invalid from_date format: {from_date_str}")
        
        if to_date_str:
            try:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d')
                to_date_end = to_date.replace(hour=23, minute=59, second=59)
                query = query.filter(MultiGRNBatch.created_at <= to_date_end)
            except ValueError:
                logging.warning(f"Invalid to_date format: {to_date_str}")
        
        query = query.order_by(MultiGRNBatch.created_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        batches = pagination.items
        
        return render_template('multi_grn/index.html', 
                             batches=batches,
                             per_page=per_page,
                             search_term=search_term,
                             from_date=from_date_str,
                             to_date=to_date_str,
                             status_filter=status_filter,
                             pagination=pagination)
    except Exception as e:
        logging.error(f"Error loading Multi GRN batches: {e}")
        flash('Error loading GRN batches', 'error')
        return redirect(url_for('dashboard'))

@multi_grn_bp.route('/delete/<int:batch_id>', methods=['POST'])
@login_required
def delete_batch(batch_id):
    """Delete a draft batch and all related data"""
    if not current_user.has_permission('multiple_grn'):
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        
        # Verify ownership
        if batch.user_id != current_user.id:
            flash('Access denied - You can only delete your own batches', 'error')
            return redirect(url_for('multi_grn.index'))
        
        # Only allow deleting draft batches
        if batch.status != 'draft':
            flash('Only draft batches can be deleted', 'warning')
            return redirect(url_for('multi_grn.index'))
        
        batch_number = batch.batch_number
        customer_name = batch.customer_name
        
        # Delete the batch (cascade will delete related po_links and line_selections)
        db.session.delete(batch)
        db.session.commit()
        
        logging.info(f"🗑️ Deleted draft batch {batch_number} for customer {customer_name}")
        flash(f'Draft batch {batch_number} has been deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting batch {batch_id}: {e}")
        flash('Error deleting batch. Please try again.', 'error')
    
    return redirect(url_for('multi_grn.index'))

@multi_grn_bp.route('/create/step1', methods=['GET', 'POST'])
@login_required
def create_step1_customer():
    """Step 1: Select Customer and Document Series"""
    if not current_user.has_permission('multiple_grn'):
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        customer_code = request.form.get('customer_code')
        customer_name = request.form.get('customer_name')
        doc_series_id = request.form.get('doc_series_id')
        doc_series_name = request.form.get('doc_series_name')
        
        if not customer_code or not customer_name:
            flash('Please select a customer', 'error')
            return redirect(url_for('multi_grn.create_step1_customer'))
        
        if not doc_series_id or not doc_series_name:
            flash('Please select a document series', 'error')
            return redirect(url_for('multi_grn.create_step1_customer'))
        
        from datetime import datetime
        batch_number = f"MGRN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        batch = MultiGRNBatch(
            user_id=current_user.id,
            batch_number=batch_number,
            customer_code=customer_code,
            customer_name=customer_name,
            doc_series_id=int(doc_series_id),
            doc_series_name=doc_series_name,
            status='draft'
        )
        db.session.add(batch)
        db.session.commit()
        
        logging.info(f"✅ Created GRN batch {batch.batch_number} for customer {customer_name} with series {doc_series_name}")
        return redirect(url_for('multi_grn.create_step2_select_pos', batch_id=batch.id))
    
    return render_template('multi_grn/step1_customer.html')

@multi_grn_bp.route('/create/step2/<int:batch_id>', methods=['GET', 'POST'])
@login_required
def create_step2_select_pos(batch_id):
    """Step 2: Select Purchase Orders filtered by Series and CardCode"""
    batch = MultiGRNBatch.query.get_or_404(batch_id)
    
    if batch.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('multi_grn.index'))
    
    if request.method == 'POST':
        selected_pos = request.form.getlist('selected_pos[]')
        
        if not selected_pos:
            flash('Please select at least one Purchase Order', 'error')
            return redirect(url_for('multi_grn.create_step2_select_pos', batch_id=batch_id))
        
        added_count = 0
        skipped_count = 0
        
        for po_data_json in selected_pos:
            po_data = json.loads(po_data_json)
            
            # Fix: Correctly read DocEntry from SQL query response (field name has quotes)
            doc_entry = po_data.get("'DocEntry'") or po_data.get('DocEntry')
            doc_num_key = "'PO_Document_Number'" if "'PO_Document_Number'" in po_data else 'DocNum'
            doc_num = po_data.get(doc_num_key)
            
            card_code_key = "'Vendor Code'" if "'Vendor Code'" in po_data else 'CardCode'
            card_code = po_data.get(card_code_key, batch.customer_code)
            
            card_name_key = "'Vendor Nam'" if "'Vendor Nam'" in po_data else 'CardName'
            card_name = po_data.get(card_name_key, batch.customer_name)
            
            posting_date_key = "'Posting Date'" if "'Posting Date'" in po_data else 'DocDate'
            posting_date_str = po_data.get(posting_date_key)
            
            existing_po_link = MultiGRNPOLink.query.filter_by(
                batch_id=batch.id,
                po_doc_num=str(doc_num)
            ).first()
            
            if not existing_po_link:
                po_date = None
                if posting_date_str:
                    try:
                        if len(str(posting_date_str)) == 8:
                            po_date = datetime.strptime(str(posting_date_str), '%Y%m%d').date()
                        else:
                            po_date = datetime.strptime(str(posting_date_str)[:10], '%Y-%m-%d').date()
                    except:
                        pass
                
                po_link = MultiGRNPOLink(
                    batch_id=batch.id,
                    po_doc_entry=int(doc_entry) if doc_entry else 0,
                    po_doc_num=str(doc_num),
                    po_card_code=card_code,
                    po_card_name=card_name,
                    po_doc_date=po_date,
                    po_doc_total=Decimal('0'),
                    status='selected'
                )
                db.session.add(po_link)
                added_count += 1
            else:
                skipped_count += 1
                logging.info(f"⚠️ PO {doc_num} already exists in batch {batch_id}, skipping")
        
        batch.total_pos = len(batch.po_links)
        db.session.commit()
        
        if added_count > 0:
            logging.info(f"✅ Added {added_count} new POs to batch {batch_id}")
            flash(f'Selected {added_count} Purchase Order(s)', 'success')
        if skipped_count > 0:
            flash(f'{skipped_count} Purchase Order(s) were already selected', 'info')
        
        return redirect(url_for('multi_grn.create_step3_select_lines', batch_id=batch_id))
    
    sap_service = SAPMultiGRNService()
    
    if batch.doc_series_id:
        result = sap_service.fetch_open_pos_by_series_and_cardcode(batch.doc_series_id, batch.customer_code)
    else:
        result = sap_service.fetch_open_purchase_orders_by_name(batch.customer_name)
    
    if not result['success']:
        flash(f"Error fetching Purchase Orders: {result.get('error')}", 'error')
        return redirect(url_for('multi_grn.index'))
    
    purchase_orders = result.get('purchase_orders', [])
    logging.info(f"📊 Found {len(purchase_orders)} open POs for series {batch.doc_series_name} and customer {batch.customer_name}")
    return render_template('multi_grn/step2_select_pos.html', batch=batch, purchase_orders=purchase_orders)

@multi_grn_bp.route('/create/step3/<int:batch_id>', methods=['GET', 'POST'])
@login_required
def create_step3_select_lines(batch_id):
    """Step 3: Select line items from POs and manage item details"""
    batch = MultiGRNBatch.query.get_or_404(batch_id)
    
    if batch.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('multi_grn.index'))
    
    if request.method == 'POST':
        # Process line selection from Step 2 (initial selection)
        lines_added = 0
        
        for po_link in batch.po_links:
            selected_lines = request.form.getlist(f'lines_po_{po_link.id}[]')
            
            for line_data_json in selected_lines:
                line_data = json.loads(line_data_json)
                qty_key = f'qty_po_{po_link.id}_line_{line_data["LineNum"]}'
                open_qty = line_data.get('OpenQuantity', line_data.get('Quantity', 0))
                selected_qty = Decimal(request.form.get(qty_key, open_qty))
                
                if selected_qty > 0:
                    # Check if line already exists to prevent duplicates
                    existing_line = MultiGRNLineSelection.query.filter_by(
                        po_link_id=po_link.id,
                        po_line_num=line_data['LineNum'],
                        item_code=line_data['ItemCode']
                    ).first()
                    
                    if not existing_line:
                        line_selection = MultiGRNLineSelection(
                            po_link_id=po_link.id,
                            po_line_num=line_data['LineNum'],
                            item_code=line_data['ItemCode'],
                            item_description=line_data.get('ItemDescription', ''),
                            ordered_quantity=Decimal(str(line_data.get('Quantity', 0))),
                            open_quantity=Decimal(str(line_data.get('OpenQuantity', line_data.get('Quantity', 0)))),
                            selected_quantity=selected_qty,
                            warehouse_code=line_data.get('WarehouseCode', ''),
                            unit_price=Decimal(str(line_data.get('UnitPrice', 0))),
                            line_status=line_data.get('LineStatus', ''),
                            inventory_type=line_data.get('ManageSerialNumbers') or line_data.get('ManageBatchNumbers') or 'standard'
                        )
                        db.session.add(line_selection)
                        lines_added += 1
                    else:
                        # Update existing line with new quantity
                        existing_line.selected_quantity = selected_qty
                        lines_added += 1
        
        if lines_added == 0:
            flash('Please select at least one line item to proceed', 'error')
            return redirect(url_for('multi_grn.create_step3_select_lines', batch_id=batch_id))
        
        db.session.commit()
        logging.info(f"✅ {lines_added} line item(s) selected for batch {batch_id}")
        flash(f'{lines_added} line item(s) selected successfully', 'success')
        # Stay on Step 3 to allow detail entry
        return redirect(url_for('multi_grn.create_step3_select_lines', batch_id=batch_id))
    
    # GET request - check if lines already exist
    has_lines = any(po_link.line_selections for po_link in batch.po_links)
    
    if has_lines:
        # Lines already selected, show detail entry view
        return render_template('multi_grn/step3_detail.html', batch=batch)
    else:
        # No lines selected yet, show line selection view
        # Fetch open line items from all selected POs using new API method
        sap_service = SAPMultiGRNService()
        po_doc_entries = [po_link.po_doc_entry for po_link in batch.po_links]
        
        result = sap_service.fetch_open_line_items(po_doc_entries)
        
        if not result['success']:
            flash(f"Error fetching line items: {result.get('error')}", 'error')
            return redirect(url_for('multi_grn.create_step2_select_pos', batch_id=batch_id))
        
        all_line_items = result.get('line_items', [])
        
        # Group line items by PO for display
        po_details = []
        for po_link in batch.po_links:
            lines_for_po = [
                line for line in all_line_items 
                if line.get('PODocEntry') == po_link.po_doc_entry
            ]
            if lines_for_po:
                po_details.append({
                    'po_link': po_link,
                    'lines': lines_for_po
                })
        
        logging.info(f"📊 Step 3 - Fetched {len(all_line_items)} open line items across {len(po_details)} POs")
        return render_template('multi_grn/step3_select_lines.html', batch=batch, po_details=po_details)

@multi_grn_bp.route('/create/step4/<int:batch_id>')
@login_required
def create_step4_review(batch_id):
    """Step 4: Review selections before posting"""
    batch = MultiGRNBatch.query.get_or_404(batch_id)
    
    if batch.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('multi_grn.index'))
    
    return render_template('multi_grn/step4_review.html', batch=batch)

@multi_grn_bp.route('/create/step5/<int:batch_id>', methods=['POST'])
@login_required
def create_step5_post(batch_id):
    """Step 5: Post GRNs to SAP B1 (requires QC approval)"""
    batch = MultiGRNBatch.query.get_or_404(batch_id)
    
    if batch.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    if batch.qc_status != 'approved':
        return jsonify({
            'success': False,
            'error': f'Batch must be QC approved before posting. Current QC status: {batch.qc_status or "not submitted"}'
        }), 400
    
    if batch.status not in ['qc_approved', 'pending_qc']:
        return jsonify({
            'success': False,
            'error': f'Batch cannot be posted from {batch.status} status'
        }), 400
    
    try:
        sap_service = SAPMultiGRNService()
        results = []
        success_count = 0
        
        for po_link in batch.po_links:
            # Idempotency check: skip already posted PO links
            if po_link.status == 'posted' or po_link.sap_grn_doc_entry:
                logging.info(f"⏭️ Skipping already posted PO link {po_link.po_doc_num} (GRN: {po_link.sap_grn_doc_num})")
                success_count += 1  # Count as success since it's already posted
                results.append({'po_num': po_link.po_doc_num, 'success': True, 'grn_num': po_link.sap_grn_doc_num, 'skipped': True})
                continue
            
            if not po_link.line_selections:
                continue
            
            document_lines = []
            line_number = 0  # 0-indexed counter for BaseLineNumber in serial/batch arrays
            
            for line in po_link.line_selections:
                # Check if this is a manual item (not from PO line)
                if line.line_status == 'manual' or line.po_line_num == -1:
                    # Manual item - no base reference to PO
                    doc_line = {
                        'ItemCode': line.item_code,
                        'Quantity': float(line.selected_quantity),
                        'WarehouseCode': line.warehouse_code or '7000-FG'
                    }
                else:
                    # PO-based item - include base reference
                    doc_line = {
                        'BaseType': 22,
                        'BaseEntry': po_link.po_doc_entry,
                        'BaseLine': line.po_line_num,
                        'ItemCode': line.item_code,
                        'Quantity': float(line.selected_quantity),
                        'WarehouseCode': line.warehouse_code or '7000-FG'
                    }
                
                # Add bin location if present
                if line.bin_location:
                    doc_line['BinAllocations'] = [{
                        'BinAbsEntry': line.bin_location,
                        'Quantity': float(line.selected_quantity)
                    }]
                
                # Build batch numbers array from MultiGRNBatchDetails
                # BaseLineNumber must be the 0-indexed position in DocumentLines array
                if line.batch_details:
                    batch_numbers = []
                    for batch_detail in line.batch_details:
                        batch_entry = {
                            'BatchNumber': batch_detail.batch_number,
                            'Quantity': float(batch_detail.quantity),
                            'BaseLineNumber': line_number  # 0-indexed position in DocumentLines
                        }
                        if batch_detail.expiry_date:
                            batch_entry['ExpiryDate'] = batch_detail.expiry_date.isoformat()
                        if batch_detail.manufacturer_serial_number:
                            batch_entry['ManufacturerSerialNumber'] = batch_detail.manufacturer_serial_number
                        if batch_detail.internal_serial_number:
                            batch_entry['InternalSerialNumber'] = batch_detail.internal_serial_number
                        batch_numbers.append(batch_entry)
                    
                    if batch_numbers:
                        doc_line['BatchNumbers'] = batch_numbers
                
                # Build serial numbers array from MultiGRNSerialDetails
                # BaseLineNumber must be the 0-indexed position in DocumentLines array
                elif line.serial_details:
                    serial_numbers = []
                    for serial_detail in line.serial_details:
                        serial_entry = {
                            'InternalSerialNumber': serial_detail.serial_number,
                            'Quantity': 1.0,  # Each serial is always quantity 1
                            'BaseLineNumber': line_number  # 0-indexed position in DocumentLines
                        }
                        if serial_detail.manufacturer_serial_number:
                            serial_entry['ManufacturerSerialNumber'] = serial_detail.manufacturer_serial_number
                        if serial_detail.expiry_date:
                            serial_entry['ExpiryDate'] = serial_detail.expiry_date.isoformat()
                        serial_numbers.append(serial_entry)
                    
                    if serial_numbers:
                        doc_line['SerialNumbers'] = serial_numbers
                
                # Fallback: Use old JSON fields if new detail models are empty (backward compatibility)
                elif line.serial_numbers:
                    serial_data = json.loads(line.serial_numbers) if isinstance(line.serial_numbers, str) else line.serial_numbers
                    doc_line['SerialNumbers'] = serial_data
                
                elif line.batch_numbers:
                    batch_data = json.loads(line.batch_numbers) if isinstance(line.batch_numbers, str) else line.batch_numbers
                    doc_line['BatchNumbers'] = batch_data
                
                document_lines.append(doc_line)
                line_number += 1  # Increment for next line
            
            grn_data = {
                'CardCode': po_link.po_card_code,
                'DocDate': date.today().isoformat(),
                'DocDueDate': date.today().isoformat(),
                'Comments': f'Auto-created from batch {batch.id}',
                'NumAtCard': f'BATCH-{batch.id}-PO-{po_link.po_doc_num}',
                'BPL_IDAssignedToInvoice': 5,
                'DocumentLines': document_lines
            }
            
            result = sap_service.create_purchase_delivery_note(grn_data)
            
            if result['success']:
                po_link.status = 'posted'
                po_link.sap_grn_doc_num = result.get('doc_num')
                po_link.sap_grn_doc_entry = result.get('doc_entry')
                po_link.posted_at = datetime.utcnow()
                po_link.error_message = None  # Clear any previous errors
                success_count += 1
                results.append({'po_num': po_link.po_doc_num, 'success': True, 'grn_num': result.get('doc_num')})
            else:
                po_link.status = 'failed'
                po_link.error_message = result.get('error')
                results.append({'po_num': po_link.po_doc_num, 'success': False, 'error': result.get('error')})
        
        # Update batch status based on results
        total_po_links = len(results)
        failed_count = total_po_links - success_count
        
        if success_count == total_po_links:
            # All succeeded - mark as completed
            batch.status = 'completed'
            batch.completed_at = datetime.utcnow()
            batch.posted_at = datetime.utcnow()
            batch.posted_by_id = current_user.id
            batch.error_log = None
        elif success_count > 0:
            # Partial success - keep as qc_approved to allow retry
            batch.status = 'qc_approved'
            batch.error_log = f"Partial completion: {success_count} of {total_po_links} PO links posted successfully. {failed_count} failed. See individual PO error messages. You can retry posting the failed items."
            logging.warning(f"⚠️ Batch {batch_id} partial completion: {success_count}/{total_po_links} succeeded")
        else:
            # All failed - keep as qc_approved to allow retry
            batch.status = 'qc_approved'
            batch.error_log = f"SAP posting failed for all {total_po_links} PO links. See individual PO error messages. You can retry posting."
            logging.error(f"❌ Batch {batch_id} posting failed for all PO links")
        
        batch.total_grns_created = success_count
        db.session.commit()
        
        if success_count == total_po_links:
            logging.info(f"✅ Batch {batch_id} completed: {success_count} GRNs created by {current_user.username}")
        
        return jsonify({
            'success': success_count > 0,  # True if at least one succeeded
            'results': results,
            'total_success': success_count,
            'total_failed': failed_count,
            'message': f'{success_count} of {total_po_links} PO links posted successfully' if success_count > 0 else 'All PO links failed to post',
            'allow_retry': failed_count > 0
        })
        
    except Exception as e:
        logging.error(f"❌ Error posting GRNs for batch {batch_id}: {str(e)}")
        # Keep batch in qc_approved state to allow retry
        batch.status = 'qc_approved'
        batch.error_log = f"System error during posting: {str(e)}. Batch remains QC approved. You can retry posting."
        db.session.commit()
        return jsonify({'success': False, 'error': str(e), 'allow_retry': True}), 500

@multi_grn_bp.route('/batch/<int:batch_id>')
@login_required
def view_batch(batch_id):
    """View batch details"""
    batch = MultiGRNBatch.query.get_or_404(batch_id)
    
    if batch.user_id != current_user.id and current_user.role not in ['admin', 'manager']:
        flash('Access denied', 'error')
        return redirect(url_for('multi_grn.index'))
    
    return render_template('multi_grn/view_batch.html', batch=batch)

@multi_grn_bp.route('/batch/<int:batch_id>/retry-posting', methods=['POST'])
@login_required
def retry_posting(batch_id):
    """Retry SAP posting for failed PO links (QC role required)"""
    try:
        if not current_user.has_permission('qc_dashboard') and current_user.role not in ['admin', 'qc', 'manager']:
            return jsonify({'success': False, 'error': 'QC or Manager permissions required'}), 403
        
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        
        # Validate batch is in qc_approved state with failures
        if batch.status != 'qc_approved':
            return jsonify({
                'success': False, 
                'error': f'Can only retry posting for QC approved batches. Current status: {batch.status}'
            }), 400
        
        # Get failed PO links (only retry those that failed)
        failed_po_links = [po_link for po_link in batch.po_links if po_link.status == 'failed']
        
        if not failed_po_links:
            return jsonify({
                'success': False,
                'error': 'No failed PO links found to retry'
            }), 400
        
        logging.info(f"🔄 Retrying posting for batch {batch_id}: {len(failed_po_links)} failed PO links by {current_user.username}")
        
        # Retry posting for failed PO links
        sap_service = SAPMultiGRNService()
        results = []
        success_count = 0
        
        for po_link in failed_po_links:
            # Skip if already posted (idempotency check)
            if po_link.sap_grn_doc_entry:
                logging.warning(f"⚠️ PO link {po_link.po_doc_num} already has SAP doc entry {po_link.sap_grn_doc_entry}, skipping")
                results.append({'po_num': po_link.po_doc_num, 'success': False, 'error': 'Already posted, skipping duplicate'})
                continue
            
            if not po_link.line_selections:
                logging.warning(f"⚠️ PO link {po_link.po_doc_num} has no line selections, skipping")
                results.append({'po_num': po_link.po_doc_num, 'success': False, 'error': 'No line selections'})
                continue
            
            # Build document lines
            document_lines = []
            line_number = 0
            
            for line in po_link.line_selections:
                if line.line_status == 'manual' or line.po_line_num == -1:
                    doc_line = {
                        'ItemCode': line.item_code,
                        'Quantity': float(line.selected_quantity),
                        'WarehouseCode': line.warehouse_code or '7000-FG'
                    }
                else:
                    doc_line = {
                        'BaseType': 22,
                        'BaseEntry': po_link.po_doc_entry,
                        'BaseLine': line.po_line_num,
                        'ItemCode': line.item_code,
                        'Quantity': float(line.selected_quantity),
                        'WarehouseCode': line.warehouse_code or '7000-FG'
                    }
                
                if line.bin_location:
                    doc_line['BinAllocations'] = [{
                        'BinAbsEntry': line.bin_location,
                        'Quantity': float(line.selected_quantity)
                    }]
                
                if line.batch_details:
                    batch_numbers = []
                    for batch_detail in line.batch_details:
                        batch_entry = {
                            'BatchNumber': batch_detail.batch_number,
                            'Quantity': float(batch_detail.quantity),
                            'BaseLineNumber': line_number
                        }
                        if batch_detail.expiry_date:
                            batch_entry['ExpiryDate'] = batch_detail.expiry_date.isoformat()
                        if batch_detail.manufacturer_serial_number:
                            batch_entry['ManufacturerSerialNumber'] = batch_detail.manufacturer_serial_number
                        if batch_detail.internal_serial_number:
                            batch_entry['InternalSerialNumber'] = batch_detail.internal_serial_number
                        batch_numbers.append(batch_entry)
                    if batch_numbers:
                        doc_line['BatchNumbers'] = batch_numbers
                
                elif line.serial_details:
                    serial_numbers = []
                    for serial_detail in line.serial_details:
                        serial_entry = {
                            'InternalSerialNumber': serial_detail.serial_number,
                            'Quantity': 1.0,
                            'BaseLineNumber': line_number
                        }
                        if serial_detail.manufacturer_serial_number:
                            serial_entry['ManufacturerSerialNumber'] = serial_detail.manufacturer_serial_number
                        if serial_detail.expiry_date:
                            serial_entry['ExpiryDate'] = serial_detail.expiry_date.isoformat()
                        serial_numbers.append(serial_entry)
                    if serial_numbers:
                        doc_line['SerialNumbers'] = serial_numbers
                
                elif line.serial_numbers:
                    serial_data = json.loads(line.serial_numbers) if isinstance(line.serial_numbers, str) else line.serial_numbers
                    doc_line['SerialNumbers'] = serial_data
                
                elif line.batch_numbers:
                    batch_data = json.loads(line.batch_numbers) if isinstance(line.batch_numbers, str) else line.batch_numbers
                    doc_line['BatchNumbers'] = batch_data
                
                document_lines.append(doc_line)
                line_number += 1
            
            grn_data = {
                'CardCode': po_link.po_card_code,
                'DocDate': date.today().isoformat(),
                'DocDueDate': date.today().isoformat(),
                'Comments': f'Retry - Auto-created from batch {batch.id}',
                'NumAtCard': f'BATCH-{batch.id}-PO-{po_link.po_doc_num}',
                'BPL_IDAssignedToInvoice': 5,
                'DocumentLines': document_lines
            }
            
            result = sap_service.create_purchase_delivery_note(grn_data)
            
            if result['success']:
                po_link.status = 'posted'
                po_link.sap_grn_doc_num = result.get('doc_num')
                po_link.sap_grn_doc_entry = result.get('doc_entry')
                po_link.posted_at = datetime.utcnow()
                po_link.error_message = None
                success_count += 1
                results.append({'po_num': po_link.po_doc_num, 'success': True, 'grn_num': result.get('doc_num')})
                logging.info(f"✅ Retry successful for PO {po_link.po_doc_num}: GRN {result.get('doc_num')}")
            else:
                po_link.error_message = f"Retry failed: {result.get('error')}"
                results.append({'po_num': po_link.po_doc_num, 'success': False, 'error': result.get('error')})
                logging.error(f"❌ Retry failed for PO {po_link.po_doc_num}: {result.get('error')}")
        
        # Update batch status
        total_retry_links = len(failed_po_links)
        failed_count = total_retry_links - success_count
        
        # Check overall batch status (including previously successful PO links)
        all_po_links = batch.po_links
        total_posted = sum(1 for po in all_po_links if po.status == 'posted')
        total_links = len(all_po_links)
        
        if total_posted == total_links:
            # All PO links now posted - mark batch as completed
            batch.status = 'completed'
            batch.completed_at = datetime.utcnow()
            batch.posted_at = datetime.utcnow()
            batch.posted_by_id = current_user.id
            batch.error_log = None
        elif success_count > 0:
            # Some retries succeeded - update error log
            batch.error_log = f"Retry partially successful: {success_count} of {total_retry_links} retried PO links posted. {total_posted} of {total_links} total PO links now posted."
        
        batch.total_grns_created = total_posted
        db.session.commit()
        
        logging.info(f"🔄 Retry completed for batch {batch_id}: {success_count}/{total_retry_links} succeeded. Overall: {total_posted}/{total_links} posted")
        
        return jsonify({
            'success': success_count > 0,
            'results': results,
            'total_success': success_count,
            'total_failed': failed_count,
            'total_posted': total_posted,
            'total_links': total_links,
            'message': f'Retry completed: {success_count} of {total_retry_links} PO links posted successfully',
            'batch_completed': batch.status == 'completed',
            'allow_retry': any(po.status == 'failed' for po in batch.po_links)
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"❌ Error retrying posting for batch {batch_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/batch/<int:batch_id>/submit-qc', methods=['POST'])
@login_required
def submit_for_qc(batch_id):
    """Submit batch for QC verification"""
    try:
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        
        if batch.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if batch.status not in ['draft', 'collecting']:
            return jsonify({'success': False, 'error': f'Batch cannot be submitted from {batch.status} status'}), 400
        
        incomplete_lines = []
        for po_link in batch.po_links:
            for line in po_link.line_selections:
                if not line.is_complete or not line.warehouse_code:
                    incomplete_lines.append(f"PO {po_link.po_doc_num} - {line.item_code}")
        
        if incomplete_lines:
            return jsonify({
                'success': False,
                'error': f'Cannot submit: {len(incomplete_lines)} line(s) incomplete',
                'incomplete_lines': incomplete_lines
            }), 400
        
        batch.status = 'pending_qc'
        batch.qc_status = 'pending'
        batch.submitted_at = datetime.utcnow()
        db.session.commit()
        
        logging.info(f"✅ Batch {batch.batch_number} submitted for QC verification")
        return jsonify({
            'success': True,
            'message': 'Batch submitted for QC verification',
            'batch_id': batch.id
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error submitting batch for QC: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/batch/<int:batch_id>/qc-approve', methods=['POST'])
@login_required
def qc_approve_batch(batch_id):
    """QC approve a batch (QC role required)"""
    try:
        if not current_user.has_permission('qc_dashboard') and current_user.role not in ['admin', 'qc']:
            return jsonify({'success': False, 'error': 'QC permissions required'}), 403
        
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        
        if batch.status != 'pending_qc':
            return jsonify({'success': False, 'error': 'Batch is not pending QC approval'}), 400
        
        data = request.get_json() or {}
        notes = data.get('notes', '')
        
        batch.status = 'qc_approved'
        batch.qc_status = 'approved'
        batch.qc_approver_id = current_user.id
        batch.qc_reviewed_at = datetime.utcnow()
        batch.qc_notes = notes
        
        for po_link in batch.po_links:
            for line in po_link.line_selections:
                line.qc_status = 'approved'
        
        db.session.commit()
        
        logging.info(f"✅ Batch {batch.batch_number} approved by QC user {current_user.username}")
        return jsonify({
            'success': True,
            'message': 'Batch approved successfully',
            'batch_id': batch.id
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error approving batch: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/batch/<int:batch_id>/qc-reject', methods=['POST'])
@login_required
def qc_reject_batch(batch_id):
    """QC reject a batch (QC role required)"""
    try:
        if not current_user.has_permission('qc_dashboard') and current_user.role not in ['admin', 'qc']:
            return jsonify({'success': False, 'error': 'QC permissions required'}), 403
        
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        
        if batch.status != 'pending_qc':
            return jsonify({'success': False, 'error': 'Batch is not pending QC approval'}), 400
        
        data = request.get_json() or {}
        notes = data.get('notes', '')
        
        if not notes:
            return jsonify({'success': False, 'error': 'Rejection notes are required'}), 400
        
        batch.status = 'qc_rejected'
        batch.qc_status = 'rejected'
        batch.qc_approver_id = current_user.id
        batch.qc_reviewed_at = datetime.utcnow()
        batch.qc_notes = notes
        
        for po_link in batch.po_links:
            for line in po_link.line_selections:
                line.qc_status = 'rejected'
        
        db.session.commit()
        
        logging.info(f"❌ Batch {batch.batch_number} rejected by QC user {current_user.username}")
        return jsonify({
            'success': True,
            'message': 'Batch rejected',
            'batch_id': batch.id
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error rejecting batch: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/batch/<int:batch_id>/reset-for-resubmission', methods=['POST'])
@login_required
def reset_batch_for_resubmission(batch_id):
    """Reset a rejected batch back to draft status for resubmission"""
    try:
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        
        if batch.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if batch.status != 'qc_rejected':
            return jsonify({'success': False, 'error': 'Only rejected batches can be reset for resubmission'}), 400
        
        batch.status = 'draft'
        batch.qc_status = 'pending'
        batch.qc_notes = None
        batch.submitted_at = None
        
        for po_link in batch.po_links:
            for line in po_link.line_selections:
                line.qc_status = 'pending'
        
        db.session.commit()
        
        logging.info(f"🔄 Batch {batch.batch_number} reset for resubmission by {current_user.username}")
        return jsonify({
            'success': True,
            'message': 'Batch reset for resubmission. You can now edit and resubmit.',
            'batch_id': batch.id
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error resetting batch: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/qc-dashboard')
@login_required
def qc_dashboard():
    """QC Dashboard to view and manage pending Multi GRN batches"""
    if not current_user.has_permission('qc_dashboard') and current_user.role not in ['admin', 'qc']:
        flash('QC dashboard access denied', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        pending_batches = MultiGRNBatch.query.filter_by(status='pending_qc').order_by(MultiGRNBatch.submitted_at.desc()).all()
        approved_batches = MultiGRNBatch.query.filter_by(status='qc_approved').order_by(MultiGRNBatch.qc_reviewed_at.desc()).limit(10).all()
        rejected_batches = MultiGRNBatch.query.filter_by(status='qc_rejected').order_by(MultiGRNBatch.qc_reviewed_at.desc()).limit(10).all()
        
        return render_template('multi_grn/qc_dashboard.html',
                             pending_batches=pending_batches,
                             approved_batches=approved_batches,
                             rejected_batches=rejected_batches)
    except Exception as e:
        logging.error(f"Error loading QC dashboard: {e}")
        flash('Error loading QC dashboard', 'error')
        return redirect(url_for('dashboard'))

@multi_grn_bp.route('/api/search-customers')
@login_required
def api_search_customers():
    """API endpoint to search customers (legacy - kept for backward compatibility)"""
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify({'customers': []})
    
    sap_service = SAPMultiGRNService()
    result = sap_service.fetch_business_partners('S')
    
    if not result['success']:
        return jsonify({'error': result.get('error')}), 500
    
    partners = result.get('partners', [])
    filtered = [p for p in partners if query.lower() in p['CardName'].lower() or query.lower() in p['CardCode'].lower()]
    
    return jsonify({'customers': filtered[:20]})

@multi_grn_bp.route('/api/customers-dropdown')
@login_required
def api_customers_dropdown():
    """API endpoint to fetch all valid customers for dropdown"""
    sap_service = SAPMultiGRNService()
    result = sap_service.fetch_all_valid_customers()
    
    if not result['success']:
        return jsonify({'success': False, 'error': result.get('error')}), 500
    
    customers = result.get('customers', [])
    return jsonify({'success': True, 'customers': customers})

@multi_grn_bp.route('/api/document-series')
@login_required
def api_document_series():
    """API endpoint to fetch PO document series"""
    sap_service = SAPMultiGRNService()
    result = sap_service.fetch_po_document_series()
    
    if not result['success']:
        return jsonify({'success': False, 'error': result.get('error')}), 500
    
    series = result.get('series', [])
    return jsonify({'success': True, 'series': series})

@multi_grn_bp.route('/api/cardcodes-by-series')
@login_required
def api_cardcodes_by_series():
    """API endpoint to fetch CardCodes filtered by SeriesID"""
    series_id_str = request.args.get('series_id')
    
    if not series_id_str:
        return jsonify({'success': False, 'error': 'series_id parameter is required'}), 400
    
    try:
        series_id = int(series_id_str)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'series_id must be a valid integer'}), 400
    
    sap_service = SAPMultiGRNService()
    result = sap_service.fetch_cardcodes_by_series(series_id)
    
    if not result['success']:
        return jsonify({'success': False, 'error': result.get('error')}), 500
    
    cardcodes = result.get('cardcodes', [])
    return jsonify({'success': True, 'cardcodes': cardcodes})

@multi_grn_bp.route('/api/open-lines/<int:batch_id>')
@login_required
def api_open_lines(batch_id):
    """API endpoint to fetch open line items from selected POs for a batch"""
    try:
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        
        # Verify ownership
        if batch.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Get all PO doc entries from batch
        po_doc_entries = [po_link.po_doc_entry for po_link in batch.po_links]
        
        if not po_doc_entries:
            return jsonify({'success': True, 'line_items': []})
        
        sap_service = SAPMultiGRNService()
        result = sap_service.fetch_open_line_items(po_doc_entries)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result.get('error')}), 500
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error fetching open line items for batch {batch_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/generate-barcode', methods=['POST'])
@login_required
def generate_barcode():
    """Generate barcode/QR code for MultiGRN item"""
    try:
        data = request.get_json()
        item_code = data.get('item_code')
        item_name = data.get('item_name', '')
        batch_number = data.get('batch_number', '')
        serial_number = data.get('serial_number', '')
        grn_doc_num = data.get('grn_doc_num', '')
        batch_id = data.get('batch_id')
        
        if not item_code:
            return jsonify({'success': False, 'error': 'Item code is required'}), 400
        
        qr_string = f"{item_code}|{grn_doc_num}|{item_name}|{batch_number or serial_number or 'N/A'}"
        
        return jsonify({
            'success': True,
            'qr_data': qr_string,
            'label_info': {
                'item_code': item_code,
                'grn_doc_num': grn_doc_num,
                'item_name': item_name,
                'batch_number': batch_number,
                'serial_number': serial_number,
                'batch_id': batch_id
            }
        })
        
    except Exception as e:
        logging.error(f"Error generating barcode: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/validate-item', methods=['POST'])
@login_required
def validate_item():
    """Validate item code and return batch/serial management info"""
    try:
        data = request.get_json()
        item_code = data.get('item_code')
        
        if not item_code:
            return jsonify({'success': False, 'error': 'Item code is required'}), 400
        
        sap_service = SAPMultiGRNService()
        
        # Validate item and get batch/serial info
        validation_result = sap_service.validate_item_code(item_code)
        
        if not validation_result['success']:
            return jsonify(validation_result), 404
        
        # Get item details (name, UoM, etc.)
        details_result = sap_service.get_item_details(item_code)
        
        if details_result['success']:
            validation_result['item_name'] = details_result['item'].get('ItemName', '')
            validation_result['uom'] = details_result['item'].get('InventoryUOM', '')
        
        return jsonify(validation_result)
        
    except Exception as e:
        logging.error(f"Error validating item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/update-line-item', methods=['POST'])
@login_required
def update_line_item():
    """Update line item details with warehouse, bin location, quantity, and number of bags"""
    try:
        data = request.get_json()
        
        line_selection_id = data.get('line_selection_id')
        quantity = data.get('quantity')
        warehouse_code = data.get('warehouse_code')
        bin_location = data.get('bin_location')
        expiration_date = data.get('expiration_date')
        number_of_bags = data.get('number_of_bags')
        
        if not line_selection_id:
            return jsonify({'success': False, 'error': 'Line selection ID is required'}), 400
        
        # Get the line selection
        line_selection = MultiGRNLineSelection.query.get(line_selection_id)
        if not line_selection:
            return jsonify({'success': False, 'error': 'Line item not found'}), 404
        
        # Update fields
        if quantity:
            line_selection.selected_quantity = Decimal(str(quantity))
        if warehouse_code:
            line_selection.warehouse_code = warehouse_code
        if bin_location:
            line_selection.bin_location = bin_location
        
        # Handle expiration date
        if expiration_date:
            try:
                from datetime import datetime
                expiry_date_obj = datetime.strptime(expiration_date, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid expiration date format'}), 400
        
        # Handle number of bags - create batch details for standard items
        if number_of_bags and int(number_of_bags) > 0:
            from modules.multi_grn_creation.models import MultiGRNBatchDetails
            
            # Clear existing batch details for this line
            MultiGRNBatchDetails.query.filter_by(line_selection_id=line_selection_id).delete()
            
            # Create new batch details for each bag
            bags_count = int(number_of_bags)
            qty_per_bag = line_selection.selected_quantity / bags_count if line_selection.selected_quantity else 0
            
            for bag_num in range(1, bags_count + 1):
                batch_detail = MultiGRNBatchDetails(
                    line_selection_id=line_selection_id,
                    batch_number=f"BAG-{bag_num}-OF-{bags_count}",
                    quantity=qty_per_bag,
                    expiry_date=expiry_date_obj if expiration_date else None,
                    admin_date=date.today(),
                    qty_per_pack=qty_per_bag,
                    no_of_packs=1
                )
                db.session.add(batch_detail)
        
        db.session.commit()
        
        logging.info(f"✅ Updated line item {line_selection_id}: Qty={quantity}, Warehouse={warehouse_code}, Bin={bin_location}, Bags={number_of_bags}")
        
        return jsonify({
            'success': True,
            'message': 'Line item updated successfully',
            'line_selection_id': line_selection_id
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating line item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/add-manual-item', methods=['POST'])
@login_required
def add_manual_item():
    """Add a manual item to a PO link"""
    try:
        # Parse and validate JSON request body
        data = request.get_json()
        if data is None:
            return jsonify({'success': False, 'error': 'Invalid or missing JSON request body'}), 400
        
        po_link_id = data.get('po_link_id')
        item_code = data.get('item_code')
        item_description = data.get('item_description')
        quantity = data.get('quantity')
        uom = data.get('uom')
        warehouse_code = data.get('warehouse_code')
        bin_location = data.get('bin_location')
        batch_number = data.get('batch_number')
        expiry_date = data.get('expiry_date')
        serial_number = data.get('serial_number')
        supplier_barcode = data.get('supplier_barcode')
        
        if not all([po_link_id, item_code, quantity]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    except Exception as parse_error:
        # Catch JSON parsing errors (BadRequest, etc.)
        return jsonify({'success': False, 'error': f'Invalid JSON format: {str(parse_error)}'}), 400
    
    try:
        
        # Validate quantity format early
        try:
            quantity_decimal = Decimal(str(quantity))
            if quantity_decimal <= 0:
                return jsonify({'success': False, 'error': 'Quantity must be positive'}), 400
        except (ValueError, TypeError, InvalidOperation):
            return jsonify({'success': False, 'error': 'Invalid quantity format (must be numeric)'}), 400
        
        po_link = MultiGRNPOLink.query.get(po_link_id)
        if not po_link:
            return jsonify({'success': False, 'error': 'PO link not found'}), 404
        
        # Check if item already exists in line selections
        existing_line = MultiGRNLineSelection.query.filter_by(
            po_link_id=po_link_id,
            item_code=item_code
        ).first()
        
        if existing_line:
            return jsonify({'success': False, 'error': 'Item already exists in this PO'}), 400
        
        # SERVER-SIDE VALIDATION: Validate item code with SAP to get canonical inventory type
        sap_service = SAPMultiGRNService()
        validation_result = sap_service.validate_item_code(item_code)
        
        if not validation_result['success']:
            return jsonify({'success': False, 'error': f'Item validation failed: {validation_result.get("error")}'}), 400
        
        # Use server-validated inventory type, not client-provided value
        inventory_type = validation_result['inventory_type']
        batch_managed = validation_result['batch_managed']
        serial_managed = validation_result['serial_managed']
        
        # Create new line selection
        line_selection = MultiGRNLineSelection(
            po_link_id=po_link_id,
            po_line_num=-1,  # Manual item, not from PO line
            item_code=item_code,
            item_description=item_description or '',
            ordered_quantity=Decimal(str(quantity)),
            open_quantity=Decimal(str(quantity)),
            selected_quantity=Decimal(str(quantity)),
            warehouse_code=warehouse_code or '7000-FG',
            bin_location=bin_location,
            unit_price=Decimal('0'),
            line_status='manual',
            inventory_type=inventory_type
        )
        
        # SERVER-SIDE VALIDATION: Handle batch/serial numbers based on server-validated type
        if batch_managed:
            batch_numbers_data = data.get('batch_numbers')
            if not batch_numbers_data:
                return jsonify({'success': False, 'error': 'Batch numbers are required for batch-managed items'}), 400
            
            # Parse JSON if string
            if isinstance(batch_numbers_data, str):
                try:
                    batch_array = json.loads(batch_numbers_data)
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'error': 'Invalid batch numbers JSON format'}), 400
            else:
                batch_array = batch_numbers_data
            
            # Validate batch array
            if not isinstance(batch_array, list) or len(batch_array) == 0:
                return jsonify({'success': False, 'error': 'At least one batch entry is required'}), 400
            
            total_batch_qty = Decimal('0')
            for idx, batch in enumerate(batch_array):
                # Validate entry is a dict
                if not isinstance(batch, dict):
                    return jsonify({'success': False, 'error': f'Batch #{idx+1}: Invalid batch entry format (must be an object)'}), 400
                
                # Validate required fields
                if not batch.get('BatchNumber'):
                    return jsonify({'success': False, 'error': f'Batch #{idx+1}: BatchNumber is required'}), 400
                if not batch.get('Quantity'):
                    return jsonify({'success': False, 'error': f'Batch #{idx+1}: Quantity is required'}), 400
                
                try:
                    batch_qty = Decimal(str(batch['Quantity']))
                    if batch_qty <= 0:
                        return jsonify({'success': False, 'error': f'Batch #{idx+1}: Quantity must be positive'}), 400
                    total_batch_qty += batch_qty
                except (ValueError, TypeError, InvalidOperation):
                    return jsonify({'success': False, 'error': f'Batch #{idx+1}: Invalid quantity format (must be numeric)'}), 400
            
            # Validate total batch quantity matches item quantity
            item_qty = Decimal(str(quantity))
            if abs(total_batch_qty - item_qty) > Decimal('0.001'):
                return jsonify({'success': False, 'error': f'Total batch quantity ({total_batch_qty}) must equal item quantity ({item_qty})'}), 400
            
            # Store normalized JSON
            line_selection.batch_numbers = json.dumps(batch_array)
        
        elif serial_managed:
            serial_numbers_data = data.get('serial_numbers')
            if not serial_numbers_data:
                return jsonify({'success': False, 'error': 'Serial numbers are required for serial-managed items'}), 400
            
            # Validate quantity is a positive integer for serial-managed items
            try:
                item_qty_decimal = Decimal(str(quantity))
                if item_qty_decimal <= 0:
                    return jsonify({'success': False, 'error': 'Quantity must be positive for serial-managed items'}), 400
                
                # Check if quantity is an integer
                if item_qty_decimal % 1 != 0:
                    return jsonify({'success': False, 'error': 'Quantity must be a whole number for serial-managed items (one serial per unit)'}), 400
                
                item_qty = int(item_qty_decimal)
            except (ValueError, TypeError, InvalidOperation):
                return jsonify({'success': False, 'error': 'Invalid quantity format (must be numeric)'}), 400
            
            # Parse JSON if string
            if isinstance(serial_numbers_data, str):
                try:
                    serial_array = json.loads(serial_numbers_data)
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'error': 'Invalid serial numbers JSON format'}), 400
            else:
                serial_array = serial_numbers_data
            
            # Validate serial array
            if not isinstance(serial_array, list) or len(serial_array) == 0:
                return jsonify({'success': False, 'error': 'At least one serial number is required'}), 400
            
            # Validate exact 1:1 ratio between serial entries and quantity
            if len(serial_array) != item_qty:
                return jsonify({'success': False, 'error': f'Number of serial entries ({len(serial_array)}) must exactly equal quantity ({item_qty})'}), 400
            
            # Validate each serial entry
            for idx, serial in enumerate(serial_array):
                # Validate entry is a dict
                if not isinstance(serial, dict):
                    return jsonify({'success': False, 'error': f'Serial #{idx+1}: Invalid serial entry format (must be an object)'}), 400
                
                # Validate required fields
                if not serial.get('ManufacturerSerialNumber'):
                    return jsonify({'success': False, 'error': f'Serial #{idx+1}: ManufacturerSerialNumber is required'}), 400
                if not serial.get('InternalSerialNumber'):
                    return jsonify({'success': False, 'error': f'Serial #{idx+1}: InternalSerialNumber is required'}), 400
            
            # Store normalized JSON
            line_selection.serial_numbers = json.dumps(serial_array)
        
        db.session.add(line_selection)
        db.session.commit()
        
        logging.info(f"✅ Manual item {item_code} added to PO link {po_link_id} (type: {inventory_type})")
        return jsonify({
            'success': True,
            'message': 'Item added successfully',
            'line_id': line_selection.id
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding manual item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/line-selections/<int:line_id>/details', methods=['GET'])
@login_required
def get_line_selection_details(line_id):
    """Get line selection details for Multi GRN (warehouse, bin, quantity, etc.)"""
    try:
        line_selection = MultiGRNLineSelection.query.get_or_404(line_id)
        
        # Check permissions
        po_link = line_selection.po_link
        batch = po_link.batch
        if batch.user_id != current_user.id and current_user.role not in ['admin', 'manager', 'qc']:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Return line selection details
        return jsonify({
            'success': True,
            'line_details': {
                'id': line_selection.id,
                'po_line_num': line_selection.po_line_num,
                'item_code': line_selection.item_code,
                'item_description': line_selection.item_description,
                'ordered_quantity': float(line_selection.ordered_quantity) if line_selection.ordered_quantity else 0,
                'open_quantity': float(line_selection.open_quantity) if line_selection.open_quantity else 0,
                'selected_quantity': float(line_selection.selected_quantity) if line_selection.selected_quantity else 0,
                'warehouse_code': line_selection.warehouse_code,
                'bin_location': line_selection.bin_location,
                'unit_price': float(line_selection.unit_price) if line_selection.unit_price else 0,
                'inventory_type': line_selection.inventory_type,
                'line_status': line_selection.line_status
            },
            'batch_details': {
                'batch_number': batch.batch_number,
                'customer_code': batch.customer_code,
                'customer_name': batch.customer_name
            },
            'po_details': {
                'po_doc_num': po_link.po_doc_num,
                'po_doc_entry': po_link.po_doc_entry,
                'po_card_code': po_link.po_card_code,
                'po_card_name': po_link.po_card_name
            }
        })
        
    except Exception as e:
        logging.error(f"Error fetching line selection details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/line-selections/<int:line_id>/batch-details', methods=['GET', 'POST'])
@login_required
def manage_batch_details(line_id):
    """Get or add batch number details for a Multi GRN line selection"""
    from modules.multi_grn_creation.models import MultiGRNBatchDetails
    import io
    import base64
    import qrcode
    
    line_selection = MultiGRNLineSelection.query.get_or_404(line_id)
    
    if request.method == 'GET':
        batches = [{
            'id': bn.id,
            'batch_number': bn.batch_number,
            'quantity': float(bn.quantity),
            'manufacturer_serial_number': bn.manufacturer_serial_number,
            'internal_serial_number': bn.internal_serial_number,
            'expiry_date': bn.expiry_date.isoformat() if bn.expiry_date else None,
            'barcode': bn.barcode,
            'grn_number': bn.grn_number,
            'qty_per_pack': float(bn.qty_per_pack) if bn.qty_per_pack else None,
            'no_of_packs': bn.no_of_packs
        } for bn in line_selection.batch_details]
        
        return jsonify({'success': True, 'batch_details': batches})
    
    elif request.method == 'POST':
        try:
            data = request.json
            
            batch_num = data.get('batch_number', '').strip()
            if not batch_num:
                return jsonify({'success': False, 'error': 'Batch number is required'}), 400
            
            quantity = float(data.get('quantity', 0))
            if quantity <= 0:
                return jsonify({'success': False, 'error': 'Quantity must be greater than 0'}), 400
            
            expiry_date_obj = None
            if data.get('expiry_date'):
                try:
                    expiry_date_obj = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({'success': False, 'error': 'Invalid expiry date format'}), 400
            
            no_of_packs = int(data.get('no_of_packs', 1))
            qty_per_pack = quantity / no_of_packs if no_of_packs > 0 else quantity
            
            barcode_data = f"BATCH:{batch_num}"
            try:
                qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
                qr.add_data(barcode_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                barcode = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"
            except Exception:
                barcode = None
            
            batch = MultiGRNBatchDetails(
                line_selection_id=line_id,
                batch_number=batch_num,
                quantity=quantity,
                manufacturer_serial_number=data.get('manufacturer_serial_number'),
                internal_serial_number=data.get('internal_serial_number'),
                expiry_date=expiry_date_obj,
                admin_date=date.today(),
                barcode=barcode,
                grn_number=data.get('grn_number'),
                qty_per_pack=qty_per_pack,
                no_of_packs=no_of_packs
            )
            
            db.session.add(batch)
            db.session.commit()
            
            logging.info(f"✅ Added batch {batch_num} for line selection {line_id}")
            return jsonify({
                'success': True,
                'batch': {
                    'id': batch.id,
                    'batch_number': batch.batch_number,
                    'quantity': float(batch.quantity),
                    'barcode': batch.barcode,
                    'no_of_packs': batch.no_of_packs
                }
            })
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding batch details: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/line-selections/<int:line_id>/serial-details', methods=['GET', 'POST'])
@login_required
def manage_serial_details(line_id):
    """Get or add serial number details for a Multi GRN line selection"""
    from modules.multi_grn_creation.models import MultiGRNSerialDetails
    import io
    import base64
    import qrcode
    
    line_selection = MultiGRNLineSelection.query.get_or_404(line_id)
    
    if request.method == 'GET':
        serials = [{
            'id': sn.id,
            'serial_number': sn.serial_number,
            'manufacturer_serial_number': sn.manufacturer_serial_number,
            'internal_serial_number': sn.internal_serial_number,
            'expiry_date': sn.expiry_date.isoformat() if sn.expiry_date else None,
            'barcode': sn.barcode,
            'grn_number': sn.grn_number,
            'qty_per_pack': float(sn.qty_per_pack) if sn.qty_per_pack else 1,
            'no_of_packs': sn.no_of_packs
        } for sn in line_selection.serial_details]
        
        return jsonify({'success': True, 'serial_details': serials})
    
    elif request.method == 'POST':
        try:
            data = request.json
            
            serial_num = data.get('serial_number', '').strip()
            if not serial_num:
                return jsonify({'success': False, 'error': 'Serial number is required'}), 400
            
            expiry_date_obj = None
            if data.get('expiry_date'):
                try:
                    expiry_date_obj = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({'success': False, 'error': 'Invalid expiry date format'}), 400
            
            barcode_data = f"SERIAL:{serial_num}"
            try:
                qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
                qr.add_data(barcode_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                barcode = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"
            except Exception:
                barcode = None
            
            serial = MultiGRNSerialDetails(
                line_selection_id=line_id,
                serial_number=serial_num,
                manufacturer_serial_number=data.get('manufacturer_serial_number'),
                internal_serial_number=data.get('internal_serial_number'),
                expiry_date=expiry_date_obj,
                admin_date=date.today(),
                barcode=barcode,
                grn_number=data.get('grn_number'),
                qty_per_pack=data.get('qty_per_pack', 1),
                no_of_packs=data.get('no_of_packs', 1)
            )
            
            db.session.add(serial)
            db.session.commit()
            
            logging.info(f"✅ Added serial {serial_num} for line selection {line_id}")
            return jsonify({
                'success': True,
                'serial': {
                    'id': serial.id,
                    'serial_number': serial.serial_number,
                    'barcode': serial.barcode
                }
            })
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding serial details: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/line-selections/<int:line_id>/non-managed-details', methods=['GET', 'POST'])
@login_required
def manage_non_managed_details(line_id):
    """Get or add non-managed item details for a Multi GRN line selection"""
    from modules.multi_grn_creation.models import MultiGRNNonManagedDetail
    from decimal import Decimal
    
    line_selection = MultiGRNLineSelection.query.get_or_404(line_id)
    
    if request.method == 'GET':
        details = [{
            'id': d.id,
            'quantity': float(d.quantity),
            'qty_per_pack': float(d.qty_per_pack) if d.qty_per_pack else None,
            'no_of_packs': d.no_of_packs,
            'pack_number': d.pack_number,
            'expiry_date': d.expiry_date.isoformat() if d.expiry_date else None,
            'admin_date': d.admin_date.isoformat() if d.admin_date and hasattr(d.admin_date, 'isoformat') else str(d.admin_date) if d.admin_date else None,
            'grn_number': d.grn_number
        } for d in line_selection.non_managed_details]
        
        return jsonify({'success': True, 'non_managed_details': details})
    
    elif request.method == 'POST':
        try:
            data = request.json
            
            quantity = float(data.get('quantity', 0))
            if quantity <= 0:
                return jsonify({'success': False, 'error': 'Quantity must be greater than 0'}), 400
            
            no_of_packs = int(data.get('no_of_packs', 1))
            qty_per_pack = quantity / no_of_packs if no_of_packs > 0 else quantity
            pack_number = int(data.get('pack_number', 1))
            
            expiry_date_obj = None
            if data.get('expiry_date'):
                try:
                    expiry_date_obj = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({'success': False, 'error': 'Invalid expiry date format'}), 400
            
            grn_number = data.get('grn_number') or f"MGN-{line_id}-{pack_number}"
            
            non_managed_detail = MultiGRNNonManagedDetail(
                line_selection_id=line_id,
                quantity=Decimal(str(quantity)),
                expiry_date=expiry_date_obj,
                admin_date=date.today(),
                grn_number=grn_number,
                qty_per_pack=Decimal(str(qty_per_pack)),
                no_of_packs=no_of_packs,
                pack_number=pack_number
            )
            
            db.session.add(non_managed_detail)
            db.session.commit()
            
            logging.info(f"✅ Added non-managed detail pack {pack_number} for line selection {line_id}")
            return jsonify({
                'success': True,
                'detail': {
                    'id': non_managed_detail.id,
                    'quantity': float(non_managed_detail.quantity),
                    'pack_number': non_managed_detail.pack_number,
                    'no_of_packs': non_managed_detail.no_of_packs
                }
            })
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding non-managed details: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

def generate_barcode_multi_grn(data):
    """Generate QR code barcode and return base64 encoded image"""
    import io
    import base64
    import qrcode
    
    try:
        if not data or len(str(data).strip()) == 0:
            logging.warning("⚠️ Empty data provided for barcode generation")
            return None
        
        data_str = str(data).strip()
        if len(data_str) > 500:
            logging.warning(f"⚠️ Barcode data too long ({len(data_str)} chars), truncating to 500")
            data_str = data_str[:500]
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data_str)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        if len(img_base64) > 100000:
            logging.warning(f"⚠️ Generated barcode too large ({len(img_base64)} bytes), skipping")
            return None
        
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        logging.error(f"❌ Error generating barcode for data '{str(data)[:50]}...': {str(e)}")
        return None

@multi_grn_bp.route('/api/generate-barcode-labels', methods=['POST'])
@login_required
def generate_barcode_labels_multi_grn():
    """
    API endpoint to generate QR code labels for Multi GRN items (Serial, Batch, and Non-managed)
    Accepts: batch_id, line_selection_id, label_type ('serial', 'batch', or 'regular')
    Returns: JSON with label data including all requested fields
    """
    try:
        data = request.get_json()
        
        batch_id = int(data.get('batch_id'))  # Convert to int for proper comparison
        line_selection_id = int(data.get('line_selection_id'))  # Convert to int
        label_type = data.get('label_type', 'batch')
        
        if not all([batch_id, line_selection_id]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: batch_id, line_selection_id'
            }), 400
        
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        line_selection = MultiGRNLineSelection.query.get_or_404(line_selection_id)
        
        if batch.user_id != current_user.id and current_user.role not in ['admin', 'manager']:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403
        
        # Ensure proper integer comparison
        if line_selection.po_link.batch_id != batch_id:
            logging.error(f"Batch ID mismatch: line_selection.po_link.batch_id={line_selection.po_link.batch_id}, batch_id={batch_id}")
            return jsonify({
                'success': False,
                'error': 'Line selection does not belong to this batch'
            }), 400
        
        grn_date = batch.created_at.strftime('%Y-%m-%d')
        doc_number = batch.batch_number or f"MGRN/{batch.id}"
        po_number = line_selection.po_link.po_doc_num
        day_of_month = batch.created_at.day
        
        labels = []
        label_counter = 1
        
        if label_type == 'serial':
            serial_details = line_selection.serial_details
            total_serials = len(serial_details)
            
            if total_serials == 0:
                return jsonify({
                    'success': False,
                    'error': 'No serial numbers found for this item'
                }), 400
            
            first_serial = serial_details[0]
            num_packs = first_serial.no_of_packs if first_serial.no_of_packs else total_serials
            qty_per_pack = first_serial.qty_per_pack if first_serial.qty_per_pack else 1
            
            if num_packs > 0 and total_serials % num_packs != 0:
                return jsonify({
                    'success': False,
                    'error': f'Data inconsistency: {total_serials} serials cannot be evenly divided into {num_packs} packs'
                }), 400
            
            serials_per_pack = total_serials // num_packs if num_packs > 0 else total_serials
            
            for pack_idx in range(1, num_packs + 1):
                pack_start = (pack_idx - 1) * serials_per_pack
                pack_end = pack_start + serials_per_pack
                pack_serials = serial_details[pack_start:pack_end]
                
                if not pack_serials:
                    return jsonify({
                        'success': False,
                        'error': f'Data inconsistency: Pack {pack_idx} has no serial numbers'
                    }), 400
                
                ref_serial = pack_serials[0]
                serial_grn = ref_serial.grn_number or doc_number
                
                serial_list = ', '.join([s.serial_number for s in pack_serials])
                
                # Generate ID in GRPO format: GRN/DD/NNNNNNNNNN using monotonic counter
                grn_id = f"GRN/{day_of_month:02d}/{label_counter:010d}"
                
                qr_data = {
                    'id': grn_id,
                    'po': po_number,
                    'item': line_selection.item_code,
                    'serial': serial_list,
                    'qty': 1,
                    'pack': f"{pack_idx} of {num_packs}",
                    'grn_date': grn_date,
                    'exp_date': ref_serial.expiry_date.strftime('%Y-%m-%d') if ref_serial.expiry_date else 'N/A'
                }
                
                import json
                qr_text = json.dumps(qr_data, separators=(',', ':'))
                qr_code_image = generate_barcode_multi_grn(qr_text)
                
                label = {
                    'sequence': label_counter,
                    'total': num_packs,
                    'pack_text': f"{pack_idx} of {num_packs}",
                    'po_number': po_number,
                    'serial_number': serial_list,
                    'quantity': float(qty_per_pack),
                    'qty_per_pack': float(qty_per_pack),
                    'no_of_packs': num_packs,
                    'grn_date': grn_date,
                    'grn_number': serial_grn,
                    'expiration_date': ref_serial.expiry_date.strftime('%Y-%m-%d') if ref_serial.expiry_date else 'N/A',
                    'item_code': line_selection.item_code,
                    'item_name': line_selection.item_description or '',
                    'doc_number': serial_grn,
                    'qr_code_image': qr_code_image,
                    'qr_data': qr_data
                }
                labels.append(label)
                label_counter += 1
        
        elif label_type == 'batch':
            batch_details = line_selection.batch_details
            
            for batch_detail in batch_details:
                num_packs = batch_detail.no_of_packs or 1
                
                for pack_idx in range(1, num_packs + 1):
                    batch_grn = batch_detail.grn_number or doc_number
                    
                    # Generate ID in GRPO format: GRN/DD/NNNNNNNNNN using monotonic counter
                    grn_id = f"GRN/{day_of_month:02d}/{label_counter:010d}"
                    
                    qr_data = {
                        'id': grn_id,
                        'po': po_number,
                        'item': line_selection.item_code,
                        'batch': batch_detail.batch_number,
                        'qty': 1,
                        'pack': f"{pack_idx} of {num_packs}",
                        'grn_date': grn_date,
                        'exp_date': batch_detail.expiry_date.strftime('%Y-%m-%d') if batch_detail.expiry_date else 'N/A'
                    }
                    
                    import json
                    qr_text = json.dumps(qr_data, separators=(',', ':'))
                    qr_code_image = generate_barcode_multi_grn(qr_text)
                    
                    label = {
                        'sequence': label_counter,
                        'total': num_packs,
                        'pack_text': f"{pack_idx} of {num_packs}",
                        'po_number': po_number,
                        'batch_number': batch_detail.batch_number,
                        'quantity': float(batch_detail.quantity),
                        'qty_per_pack': float(batch_detail.qty_per_pack) if batch_detail.qty_per_pack else float(batch_detail.quantity),
                        'no_of_packs': num_packs,
                        'grn_date': grn_date,
                        'grn_number': f"{batch_grn}-{pack_idx}",
                        'expiration_date': batch_detail.expiry_date.strftime('%Y-%m-%d') if batch_detail.expiry_date else 'N/A',
                        'item_code': line_selection.item_code,
                        'item_name': line_selection.item_description or '',
                        'doc_number': f"{batch_grn}-{pack_idx}",
                        'qr_code_image': qr_code_image,
                        'qr_data': qr_data
                    }
                    labels.append(label)
                    label_counter += 1
        
        else:
            # Generate ID in GRPO format: GRN/DD/NNNNNNNNNN using monotonic counter
            grn_id = f"GRN/{day_of_month:02d}/{label_counter:010d}"
            
            qr_data = {
                'id': grn_id,
                'po': po_number,
                'item': line_selection.item_code,
                'qty': 1,
                'pack': '1 of 1',
                'grn_date': grn_date,
                'exp_date': 'N/A'
            }
            
            import json
            qr_text = json.dumps(qr_data, separators=(',', ':'))
            qr_code_image = generate_barcode_multi_grn(qr_text)
            
            label = {
                'sequence': label_counter,
                'total': 1,
                'pack_text': '1 of 1',
                'po_number': po_number,
                'quantity': float(line_selection.selected_quantity),
                'grn_date': grn_date,
                'grn_number': doc_number,
                'expiration_date': 'N/A',
                'item_code': line_selection.item_code,
                'item_name': line_selection.item_description or '',
                'doc_number': doc_number,
                'qr_code_image': qr_code_image,
                'qr_data': qr_data
            }
            labels.append(label)
        
        return jsonify({
            'success': True,
            'labels': labels,
            'batch_id': batch_id,
            'line_selection_id': line_selection_id,
            'label_type': label_type,
            'total_labels': len(labels)
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid value: {str(e)}'
        }), 400
    except Exception as e:
        logging.error(f"Error generating barcode labels: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@multi_grn_bp.route('/validate-item/<string:item_code>', methods=['GET'])
@login_required
def validate_item_code(item_code):
    """Validate ItemCode and return batch/serial requirements (reuses SAP validation)"""
    try:
        from sap_integration import SAPIntegration
        
        sap = SAPIntegration()
        validation_result = sap.validate_item_code(item_code)
        
        logging.info(f"🔍 Multi GRN ItemCode validation for {item_code}: {validation_result}")
        
        return jsonify(validation_result)
        
    except Exception as e:
        logging.error(f"Error validating ItemCode {item_code}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'item_code': item_code,
            'batch_required': False,
            'serial_required': False,
            'manage_method': 'N'
        }), 500

@multi_grn_bp.route('/batch/<int:batch_id>/add-item', methods=['POST'])
@login_required
def add_item_to_batch(batch_id):
    """Add item to Multi GRN batch with batch/serial details and number of bags support"""
    from modules.multi_grn_creation.models import MultiGRNBatchDetails, MultiGRNSerialDetails
    from sap_integration import SAPIntegration
    
    try:
        batch = MultiGRNBatch.query.get_or_404(batch_id)
        
        # Verify ownership
        if batch.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        if batch.status != 'draft':
            return jsonify({'success': False, 'error': 'Cannot add items to non-draft batch'}), 400
        
        # Get form data
        item_code = request.form.get('item_code')
        item_name = request.form.get('item_name')
        quantity = float(request.form.get('quantity', 0))
        unit_of_measure = request.form.get('unit_of_measure')
        warehouse_code = request.form.get('warehouse_code')
        bin_location = request.form.get('bin_location')
        batch_number = request.form.get('batch_number')
        expiry_date = request.form.get('expiry_date')
        serial_numbers_json = request.form.get('serial_numbers_json', '')
        batch_numbers_json = request.form.get('batch_numbers_json', '')
        number_of_bags = int(request.form.get('number_of_bags', 1))
        po_link_id = request.form.get('po_link_id')  # Optional: if adding from PO line
        po_line_num = request.form.get('po_line_num', -1)  # -1 for manual items
        
        if not all([item_code, item_name, quantity > 0]):
            return jsonify({'success': False, 'error': 'Item Code, Item Name, and Quantity are required'}), 400
        
        # Validate item code with SAP
        sap = SAPIntegration()
        validation_result = sap.validate_item_code(item_code)
        
        is_batch_managed = validation_result.get('batch_required', False)
        is_serial_managed = validation_result.get('serial_required', False)
        
        logging.info(f"🔍 Item {item_code} validation: Batch={is_batch_managed}, Serial={is_serial_managed}")
        
        # Block serial-managed items (UI not implemented yet)
        if is_serial_managed:
            return jsonify({
                'success': False,
                'error': 'Serial-managed items are not currently supported in Multi GRN. Please use standard GRPO for serial items.'
            }), 400
        
        # Parse expiry date if provided
        expiry_date_obj = None
        if expiry_date:
            try:
                expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid expiry date format. Use YYYY-MM-DD'}), 400
        
        # Create line selection with admin_date, expiry_date, and pack info
        line_selection = MultiGRNLineSelection(
            po_link_id=int(po_link_id) if po_link_id else batch.po_links[0].id,
            po_line_num=int(po_line_num),
            item_code=item_code,
            item_description=item_name,
            ordered_quantity=Decimal(str(quantity)),
            open_quantity=Decimal(str(quantity)),
            selected_quantity=Decimal(str(quantity)),
            warehouse_code=warehouse_code,
            bin_location=bin_location,
            unit_of_measure=unit_of_measure,
            line_status='manual' if int(po_line_num) == -1 else 'po_based',
            batch_required='Y' if is_batch_managed else 'N',
            serial_required='Y' if is_serial_managed else 'N',
            manage_method='B' if is_batch_managed else ('S' if is_serial_managed else 'N'),
            admin_date=date.today(),
            expiry_date=expiry_date_obj,
            qty_per_pack=Decimal(str(quantity / number_of_bags)) if number_of_bags > 0 else Decimal(str(quantity)),
            no_of_packs=number_of_bags,
            is_complete=True
        )
        
        db.session.add(line_selection)
        db.session.flush()
        
        # Handle serial numbers
        if is_serial_managed and serial_numbers_json:
            try:
                serial_numbers = json.loads(serial_numbers_json)
                
                if len(serial_numbers) != int(quantity):
                    db.session.rollback()
                    return jsonify({'success': False, 'error': f'Serial managed item requires {int(quantity)} serial numbers'}), 400
                
                # Validate bags can evenly divide serials
                if len(serial_numbers) % number_of_bags != 0:
                    db.session.rollback()
                    return jsonify({'success': False, 'error': f'Number of serials must be evenly divisible by number of bags'}), 400
                
                qty_per_pack = len(serial_numbers) / number_of_bags
                
                for idx, serial_data in enumerate(serial_numbers):
                    # Generate unique GRN number
                    grn_number = f"MGN-{batch.id}-{line_selection.id}-{idx+1}"
                    
                    serial = MultiGRNSerialDetails(
                        line_selection_id=line_selection.id,
                        serial_number=serial_data.get('internal_serial_number'),
                        manufacturer_serial_number=serial_data.get('manufacturer_serial_number', ''),
                        internal_serial_number=serial_data.get('internal_serial_number'),
                        expiry_date=datetime.strptime(serial_data['expiry_date'], '%Y-%m-%d').date() if serial_data.get('expiry_date') else expiry_date_obj,
                        admin_date=date.today(),
                        grn_number=grn_number,
                        qty_per_pack=qty_per_pack,
                        no_of_packs=number_of_bags
                    )
                    db.session.add(serial)
                
                logging.info(f"✅ Added {len(serial_numbers)} serial numbers for item {item_code}")
                
            except json.JSONDecodeError:
                db.session.rollback()
                return jsonify({'success': False, 'error': 'Invalid serial numbers data format'}), 400
        
        # Handle batch numbers
        if is_batch_managed and (batch_numbers_json or batch_number):
            try:
                # Handle simple batch number input or structured JSON
                if batch_numbers_json:
                    batch_numbers = json.loads(batch_numbers_json)
                elif batch_number:
                    # Create simple batch structure from single batch number
                    batch_numbers = [{
                        'batch_number': batch_number,
                        'quantity': quantity,
                        'expiry_date': expiry_date
                    }]
                else:
                    batch_numbers = []
                
                if batch_numbers:
                    total_batch_qty = sum(float(b.get('quantity', 0)) for b in batch_numbers)
                    if abs(total_batch_qty - quantity) > 0.001:
                        db.session.rollback()
                        return jsonify({'success': False, 'error': f'Total batch quantity must equal item quantity'}), 400
                    
                    for idx, batch_data in enumerate(batch_numbers):
                        batch_qty = float(batch_data.get('quantity', 0))
                        
                        # Validate bags can evenly divide batch quantity
                        if number_of_bags > 1 and batch_qty % number_of_bags != 0:
                            db.session.rollback()
                            return jsonify({'success': False, 'error': f'Batch quantity must be evenly divisible by number of bags'}), 400
                        
                        qty_per_pack = batch_qty / number_of_bags if number_of_bags > 0 else batch_qty
                        grn_number = f"MGN-{batch.id}-{line_selection.id}-{idx+1}"
                        
                        batch_detail = MultiGRNBatchDetails(
                            line_selection_id=line_selection.id,
                            batch_number=batch_data.get('batch_number'),
                            quantity=batch_qty,
                            manufacturer_serial_number=batch_data.get('manufacturer_serial_number', ''),
                            internal_serial_number=batch_data.get('internal_serial_number', ''),
                            expiry_date=datetime.strptime(batch_data['expiry_date'], '%Y-%m-%d').date() if batch_data.get('expiry_date') else expiry_date_obj,
                            admin_date=date.today(),
                            grn_number=grn_number,
                            qty_per_pack=qty_per_pack,
                            no_of_packs=number_of_bags
                        )
                        db.session.add(batch_detail)
                    
                    logging.info(f"✅ Added {len(batch_numbers)} batch numbers for item {item_code}")
                
            except json.JSONDecodeError:
                db.session.rollback()
                return jsonify({'success': False, 'error': 'Invalid batch numbers data format'}), 400
        
        # Handle non-managed items with bags
        if not is_batch_managed and not is_serial_managed:
            # For non-managed items, create non_managed_detail records to track packs
            qty_per_pack = quantity / number_of_bags if number_of_bags > 1 else quantity
            
            for pack_idx in range(1, number_of_bags + 1):
                grn_number = f"MGN-{batch.id}-{line_selection.id}-{pack_idx}"
                
                non_managed_detail = MultiGRNNonManagedDetail(
                    line_selection_id=line_selection.id,
                    quantity=Decimal(str(qty_per_pack)),
                    expiry_date=expiry_date if expiry_date else None,
                    admin_date=date.today().isoformat() if date.today() else None,
                    grn_number=grn_number,
                    qty_per_pack=Decimal(str(qty_per_pack)),
                    no_of_packs=number_of_bags,
                    pack_number=pack_idx
                )
                db.session.add(non_managed_detail)
            
            logging.info(f"✅ Added {number_of_bags} pack(s) for non-managed item {item_code}")
        
        db.session.commit()
        
        flash(f'Item {item_code} added successfully with {number_of_bags} bag(s)', 'success')
        return jsonify({
            'success': True,
            'message': f'Item {item_code} added successfully',
            'line_selection_id': line_selection.id,
            'number_of_bags': number_of_bags
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding item to batch: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@multi_grn_bp.route('/api/get-bins', methods=['GET'])
@login_required
def get_bin_locations():
    """Get bin locations for a specific warehouse"""
    try:
        warehouse_code = request.args.get('warehouse')
        if not warehouse_code:
            return jsonify({'success': False, 'error': 'Warehouse code required'}), 400
        
        from sap_integration import SAPIntegration
        sap = SAPIntegration()
        result = sap.get_bin_locations_list(warehouse_code)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify({'success': True, 'bins': []})
            
    except Exception as e:
        logging.error(f"Error getting bin locations: {str(e)}")
        return jsonify({'success': True, 'bins': []})

