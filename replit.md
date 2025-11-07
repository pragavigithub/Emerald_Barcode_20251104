# Warehouse Management System (WMS)

## Overview
A Flask-based Warehouse Management System (WMS) designed to streamline inventory operations by integrating seamlessly with SAP for functionalities such as barcode scanning, goods receipt, pick list generation, and inventory transfers. The system aims to enhance efficiency, accuracy, and control over warehouse logistics, ultimately minimizing manual errors and maximizing throughput for small to medium-sized enterprises.

## User Preferences
*   Keep MySQL migration files updated when database schema changes occur
*   SQL query validation should only run on initial startup, not on every application restart

## Recent Changes

### 2025-11-07
*   **Multi GRN Module Enhancement - Complete QR Label Generation (GRPO-Style)**: Implemented comprehensive QR code label generation for Multi GRN module matching GRPO functionality exactly. Created new endpoint `/api/generate-barcode-labels` that generates professional QR labels for Serial, Batch, and Non-managed items. For serial items, generates one label per pack (not per serial) with serial lists and manufacturer tracking. For batch items, generates labels for each pack within each batch with expiry dates and quantities. For regular items, generates standard labels with item and quantity information. All labels include complete metadata (PO number, GRN date, item details, pack numbers) and base64-encoded QR code images for printing. Enhanced Multi GRN module with comprehensive batch/serial number entry system. Added database models (MultiGRNBatchDetails, MultiGRNSerialDetails) to track detailed batch and serial information. Implemented API endpoints for batch/serial management and updated SAP B1 posting logic to build proper BatchNumbers and SerialNumbers arrays from detail models. Created MySQL migration file (`mysql_multi_grn_batch_serial_details.sql`) for schema changes. The module now supports the complete workflow: PO selection → Item selection → Batch/Serial entry → **QR Label Generation** → SAP B1 posting with full tracking.
*   **Direct Inventory Transfer Pagination and Filtering**: Implemented comprehensive pagination, filtering, and search functionality for the Direct Inventory Transfer details screen. Added date-wise filtering (from/to dates), real-time search across transfer numbers, warehouses, and notes, status filtering (Draft/Submitted/QC Approved/Posted/Rejected), and configurable pagination with rows per page selector (5/10/25/50/100). All filter parameters are preserved across page navigation. Search functionality includes 500ms debounce for optimal performance. Implementation follows the same pattern as other enhanced modules (GRPO, Inventory Counting, etc.) with all filtering logic at the query level using SQLAlchemy.
*   **Direct Inventory Transfer Auto-Validation Enhancement**: Implemented automatic item code validation when QR labels are scanned, eliminating the need for manual "Validate" button clicks. The system now validates automatically with a 500ms debounce when users scan QR labels or enter item codes, displaying real-time loading and success indicators. Enhanced UX with automatic field focus on serial/batch inputs after validation for faster data entry.
*   **Direct Inventory Transfer Bin Location Dropdowns**: Converted bin location fields from manual text inputs to dynamic dropdowns populated from SAP B1 using the `GetBinCodeByWHCode` SQL Query. Bin locations now auto-load when warehouses are selected, with loading indicators and error handling. Added new API endpoint `/direct-inventory-transfer/api/get-bin-locations` that integrates with SAP B1's `get_bin_locations_list()` method for real-time bin data fetching.
*   **QR Label Scanning for Inventory Transfer**: Added comprehensive QR label scanning functionality to the Inventory Transfer detail page with camera-based scanning and automatic item population. Implemented `/api/scan-qr-label` endpoint that supports two QR formats: Format 1 (ItemCode|TransferNumber|ItemName|BatchNumber) and Format 2 (TRANSFER:ItemCode|TransferNumber|FROM:WH|TO:WH|UNIT:X/Y|BATCH:BatchNum). The API automatically detects item type (Serial/Batch/Non-Managed) via SAP B1 validation, resolves warehouses using transfer record fallback for Format 1, and fetches real-time availability data from SAP B1 using `get_available_serial_numbers`, `get_batch_managed_item_warehouses`, and `get_non_managed_item_warehouses` methods. The frontend JavaScript auto-populates the Add Item modal with item details, serial/batch numbers, quantities, and warehouse information, streamlining the transfer workflow by eliminating manual data entry.

### 2025-11-05
*   **Advanced Filtering and Pagination Enhancements**: Implemented comprehensive filtering capabilities across four key modules: GRPO Details, Sales Order Against Delivery Details, Inventory Counting History, and Inventory Transfer. All four modules now feature date-wise filtering (from/to dates), real-time search functionality, configurable pagination with rows per page selector (5/10/25/50/100), and proper filter parameter preservation across page navigation. All filtering logic is implemented at the query level using SQLAlchemy with no database schema changes required. The implementation follows Flask and SQLAlchemy best practices with proper parameter handling and pagination URLs that preserve filter state.
*   **Multi GRN Template Fix**: Resolved template loading issue in Multi GRN module by adding `template_folder='templates'` parameter to the blueprint definition, eliminating TemplateNotFound errors.

### 2025-11-04
*   **Enhanced GRPO Warehouse and Bin Location UX**: Modified GRPO module to improve warehouse and bin location selection workflow. The warehouse field is now read-only and automatically populated from the Purchase Order data, eliminating manual selection errors. Implemented dynamic bin location fetching using SAP B1 SQL Query API (`GetBinCodeByWHCode`) with POST request, which loads bin codes based on the warehouse from the PO. This ensures accurate bin selection and streamlines the goods receipt process.

### 2025-11-03
*   **Optimized SAP SQL Query Validation**: Modified SAP B1 SQL query validation to run only on initial startup instead of every restart, improving startup performance and avoiding repeated connection attempts when SAP is unavailable. Implemented flag-based system at `.local/state/sap_queries_validated.flag` that records validation attempts (success/failure) and prevents re-runs on subsequent restarts. Added `FORCE_SAP_VALIDATION` environment variable to allow manual re-validation when needed.

### 2025-10-31
*   **Fixed Inventory Counting UI Issue**: Resolved issue where SAP Inventory Counting documents (counted and posted) were not displaying in the UI. Added dashboard statistics card, recent activities section, and comprehensive history page (`/inventory_counting_history`) to view all counted documents with filtering capabilities.

## System Architecture
The system is built on a Flask web application backend, utilizing Jinja2 for server-side rendering. A core architectural decision is the deep integration with the SAP B1 Service Layer API for all critical warehouse operations, ensuring data consistency and real-time updates. PostgreSQL is the primary database target for cloud deployments, with SQLite serving as a fallback. User authentication uses Flask-Login with robust role-based access control. The application is designed for production deployment using Gunicorn with autoscale capabilities.

**Key Features:**
*   **User Management:** Comprehensive authentication, role-based access, and self-service profile management with deactivation for audit trails.
*   **GRPO Management:** Standard Goods Receipt PO processing, intelligent batch/serial field management, and a module for batch creation of multiple GRNs from multiple Purchase Orders via a 5-step workflow with SAP B1 integration. It includes dynamic batch/serial detection and specific entry processes for serial and batch numbers.
*   **Inventory Transfer:** Enhanced module for creating inventory transfer requests with document series selection and SAP B1 validation. Includes ItemCode validation with automatic item type detection (Serial/Batch/Non-Managed) and dynamic warehouse selection based on real-time SAP B1 data using SQL Query APIs (`GetSerialManagedItemWH`, `GetBatchManagedItemWH`, `GetNonSerialNonBatchManagedItemWH`).
*   **Direct Inventory Transfer:** Barcode-based inventory transfer module with automatic serial/batch detection, real-time SAP B1 validation, intelligent serial number tracking, batch number validation, warehouse and bin selection via SAP, QC approval workflow, and direct posting to SAP B1 as StockTransfers documents.
*   **Sales Order Against Delivery:** Module for creating Delivery Notes against Sales Orders with SAP B1 integration, including SO series dropdown selection with proper series name display, cascading dropdown for open SO document numbers (using SQL Query `Get_Open_SO_DocNum` with OData fallback), document loading, item picking with batch/serial validation, individual QR code label generation, and direct SAP B1 posting. The module follows the same UI pattern as GRPO for consistency.
*   **Pick List Management:** Generation and processing of pick lists.
*   **Barcode Scanning:** Integrated camera-based scanning for various modules (GRPO, Bin Scanning, Pick List, Inventory Transfer, Barcode Reprint).
*   **Inventory Counting:** SAP B1 integrated inventory counting with local PostgreSQL database storage for tracking, audit trails, user tracking, and timestamps. Includes a comprehensive history view for all counted and posted documents, with dashboard integration showing statistics and recent counting activities.
*   **Branch Management:** Functionality for managing different warehouse branches.
*   **Quality Control Dashboard:** Provides oversight for quality processes.
*   **UI/UX:** Focuses on intuitive workflows for managing inventory, including serial number transfers and real-time validation against SAP B1.
*   **Database Migrations:** A comprehensive MySQL migration tracking system is in place for schema changes, complementing the primary PostgreSQL strategy.

**Technical Implementations:**
*   **SAP B1 Integration:** Utilizes a dedicated `SAPMultiGRNService` class for secure and robust communication with the SAP B1 Service Layer, including SSL/TLS verification and optimized OData filtering.
*   **Modular Design:** New features are implemented as modular blueprints with their own templates and services.
*   **Frontend:** Jinja2 templating with JavaScript libraries like Select2 for enhanced UI components.
*   **Error Handling:** Comprehensive validation and error logging for API communications and user inputs.

## External Dependencies
*   **SAP B1 Service Layer API**: For all core inventory and document management functionalities (GRPO, pick lists, inventory transfers, serial numbers, business partners, inventory counts).
*   **PostgreSQL**: Primary relational database for production environments.
*   **SQLite**: Local relational database for development and initial setup.
*   **Gunicorn**: WSGI HTTP server for deploying the Flask application in production.
*   **Flask-Login**: Library for managing user sessions and authentication.