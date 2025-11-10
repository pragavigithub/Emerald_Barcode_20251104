#!/usr/bin/env python3
"""
MySQL Migration: Add QC and Detail Fields to Multi GRN Tables
Adds missing columns for QC workflow, document series, and detail management
to Multi GRN tables to match PostgreSQL schema.

ADDS:
✅ QC workflow columns to multi_grn_batches (qc_status, qc_approver_id, etc.)
✅ Document series columns to multi_grn_batches (doc_series_id, doc_series_name)
✅ Detail columns to multi_grn_line_selections (is_complete, qc_status, admin_date, expiry_date, qty_per_pack, no_of_packs)
✅ multi_grn_non_managed_details table for non-batch/non-serial items

Run with: python mysql_multi_grn_qc_and_details_migration.py
"""

import os
import sys
import logging
import pymysql
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiGRNQCAndDetailsMigration:
    def __init__(self):
        self.connection = None
        self.cursor = None
    
    def get_database_config(self):
        """Get database configuration from environment or user input"""
        config = {
            'host': os.getenv('MYSQL_HOST') or input('MySQL Host (localhost): ') or 'localhost',
            'port': int(os.getenv('MYSQL_PORT') or input('MySQL Port (3306): ') or '3306'),
            'user': os.getenv('MYSQL_USER') or input('MySQL User (root): ') or 'root',
            'password': os.getenv('MYSQL_PASSWORD') or input('MySQL Password: '),
            'database': os.getenv('MYSQL_DATABASE') or input('Database Name (wms_db): ') or 'wms_db',
            'charset': 'utf8mb4',
            'autocommit': False
        }
        return config
    
    def connect(self, config):
        """Connect to MySQL database"""
        try:
            self.connection = pymysql.connect(**config)
            self.cursor = self.connection.cursor()
            logger.info(f"✅ Connected to MySQL: {config['database']}")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def column_exists(self, table_name, column_name):
        """Check if a column exists in a table"""
        self.cursor.execute(f"""
            SELECT COUNT(*) as count 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = '{table_name}' 
            AND COLUMN_NAME = '{column_name}'
        """)
        result = self.cursor.fetchone()
        return result and result[0] > 0
    
    def table_exists(self, table_name):
        """Check if a table exists"""
        self.cursor.execute(f"""
            SELECT COUNT(*) as count 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = '{table_name}'
        """)
        result = self.cursor.fetchone()
        return result and result[0] > 0
    
    def add_multi_grn_batches_columns(self):
        """Add QC and document series columns to multi_grn_batches"""
        logger.info("\n📋 Adding columns to multi_grn_batches...")
        
        columns = [
            {
                'name': 'doc_series_id',
                'sql': "ALTER TABLE multi_grn_batches ADD COLUMN doc_series_id INT NULL AFTER customer_name"
            },
            {
                'name': 'doc_series_name',
                'sql': "ALTER TABLE multi_grn_batches ADD COLUMN doc_series_name VARCHAR(200) NULL AFTER doc_series_id"
            },
            {
                'name': 'qc_status',
                'sql': "ALTER TABLE multi_grn_batches ADD COLUMN qc_status VARCHAR(20) DEFAULT 'pending' NULL AFTER completed_at"
            },
            {
                'name': 'qc_approver_id',
                'sql': "ALTER TABLE multi_grn_batches ADD COLUMN qc_approver_id INT NULL AFTER qc_status, ADD FOREIGN KEY (qc_approver_id) REFERENCES users(id)"
            },
            {
                'name': 'qc_reviewed_at',
                'sql': "ALTER TABLE multi_grn_batches ADD COLUMN qc_reviewed_at DATETIME NULL AFTER qc_approver_id"
            },
            {
                'name': 'qc_notes',
                'sql': "ALTER TABLE multi_grn_batches ADD COLUMN qc_notes TEXT NULL AFTER qc_reviewed_at"
            },
            {
                'name': 'submitted_at',
                'sql': "ALTER TABLE multi_grn_batches ADD COLUMN submitted_at DATETIME NULL AFTER qc_notes"
            },
            {
                'name': 'posted_by_id',
                'sql': "ALTER TABLE multi_grn_batches ADD COLUMN posted_by_id INT NULL AFTER submitted_at, ADD FOREIGN KEY (posted_by_id) REFERENCES users(id)"
            }
        ]
        
        added_count = 0
        for col in columns:
            if self.column_exists('multi_grn_batches', col['name']):
                logger.info(f"⏭️  Skipping {col['name']} - already exists")
            else:
                try:
                    self.cursor.execute(col['sql'])
                    self.connection.commit()
                    logger.info(f"✅ Added column: {col['name']}")
                    added_count += 1
                except Exception as e:
                    logger.error(f"❌ Error adding {col['name']}: {e}")
                    self.connection.rollback()
                    return False
        
        logger.info(f"✅ Added {added_count} columns to multi_grn_batches")
        return True
    
    def add_multi_grn_line_selections_columns(self):
        """Add detail management columns to multi_grn_line_selections"""
        logger.info("\n📋 Adding columns to multi_grn_line_selections...")
        
        columns = [
            {
                'name': 'is_complete',
                'sql': "ALTER TABLE multi_grn_line_selections ADD COLUMN is_complete BOOLEAN DEFAULT FALSE AFTER barcode_generated"
            },
            {
                'name': 'qc_status',
                'sql': "ALTER TABLE multi_grn_line_selections ADD COLUMN qc_status VARCHAR(20) DEFAULT 'pending' NULL AFTER is_complete"
            },
            {
                'name': 'admin_date',
                'sql': "ALTER TABLE multi_grn_line_selections ADD COLUMN admin_date DATE NULL AFTER qc_status"
            },
            {
                'name': 'expiry_date',
                'sql': "ALTER TABLE multi_grn_line_selections ADD COLUMN expiry_date DATE NULL AFTER admin_date"
            },
            {
                'name': 'qty_per_pack',
                'sql': "ALTER TABLE multi_grn_line_selections ADD COLUMN qty_per_pack DECIMAL(15, 3) NULL AFTER expiry_date"
            },
            {
                'name': 'no_of_packs',
                'sql': "ALTER TABLE multi_grn_line_selections ADD COLUMN no_of_packs INT DEFAULT 1 AFTER qty_per_pack"
            }
        ]
        
        added_count = 0
        for col in columns:
            if self.column_exists('multi_grn_line_selections', col['name']):
                logger.info(f"⏭️  Skipping {col['name']} - already exists")
            else:
                try:
                    self.cursor.execute(col['sql'])
                    self.connection.commit()
                    logger.info(f"✅ Added column: {col['name']}")
                    added_count += 1
                except Exception as e:
                    logger.error(f"❌ Error adding {col['name']}: {e}")
                    self.connection.rollback()
                    return False
        
        logger.info(f"✅ Added {added_count} columns to multi_grn_line_selections")
        return True
    
    def create_non_managed_details_table(self):
        """Create multi_grn_non_managed_details table"""
        logger.info("\n📋 Creating multi_grn_non_managed_details table...")
        
        if self.table_exists('multi_grn_non_managed_details'):
            logger.info("⏭️  Table multi_grn_non_managed_details already exists")
            return True
        
        try:
            self.cursor.execute("""
                CREATE TABLE multi_grn_non_managed_details (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    line_selection_id INT NOT NULL,
                    quantity DECIMAL(15, 3) NOT NULL,
                    expiry_date VARCHAR(50),
                    admin_date VARCHAR(50),
                    grn_number VARCHAR(50),
                    qty_per_pack DECIMAL(15, 3),
                    no_of_packs INT,
                    pack_number INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (line_selection_id) REFERENCES multi_grn_line_selections(id) ON DELETE CASCADE,
                    INDEX idx_non_managed_line_selection (line_selection_id),
                    INDEX idx_non_managed_grn (grn_number),
                    INDEX idx_non_managed_pack (pack_number)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            self.connection.commit()
            logger.info("✅ Created table: multi_grn_non_managed_details")
            return True
        except Exception as e:
            logger.error(f"❌ Error creating table: {e}")
            self.connection.rollback()
            return False
    
    def verify_migration(self):
        """Verify that all changes have been applied"""
        logger.info("\n📊 Verifying migration...")
        
        all_good = True
        
        # Check multi_grn_batches columns
        batches_columns = ['doc_series_id', 'doc_series_name', 'qc_status', 'qc_approver_id', 
                          'qc_reviewed_at', 'qc_notes', 'submitted_at', 'posted_by_id']
        for col in batches_columns:
            if self.column_exists('multi_grn_batches', col):
                logger.info(f"✅ multi_grn_batches.{col} exists")
            else:
                logger.error(f"❌ multi_grn_batches.{col} NOT FOUND")
                all_good = False
        
        # Check multi_grn_line_selections columns
        line_columns = ['is_complete', 'qc_status', 'admin_date', 'expiry_date', 
                       'qty_per_pack', 'no_of_packs']
        for col in line_columns:
            if self.column_exists('multi_grn_line_selections', col):
                logger.info(f"✅ multi_grn_line_selections.{col} exists")
            else:
                logger.error(f"❌ multi_grn_line_selections.{col} NOT FOUND")
                all_good = False
        
        # Check table
        if self.table_exists('multi_grn_non_managed_details'):
            logger.info("✅ multi_grn_non_managed_details table exists")
        else:
            logger.error("❌ multi_grn_non_managed_details table NOT FOUND")
            all_good = False
        
        return all_good
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("🔌 Database connection closed")

def main():
    """Main migration execution"""
    print("=" * 70)
    print("Multi GRN QC and Details Migration")
    print("=" * 70)
    print()
    
    migrator = MultiGRNQCAndDetailsMigration()
    
    try:
        # Get database config
        config = migrator.get_database_config()
        
        # Connect to database
        if not migrator.connect(config):
            print("\n❌ Failed to connect to database")
            sys.exit(1)
        
        # Run migrations
        print("\n🚀 Starting migration...\n")
        
        if not migrator.add_multi_grn_batches_columns():
            print("\n❌ Failed to add multi_grn_batches columns")
            sys.exit(1)
        
        if not migrator.add_multi_grn_line_selections_columns():
            print("\n❌ Failed to add multi_grn_line_selections columns")
            sys.exit(1)
        
        if not migrator.create_non_managed_details_table():
            print("\n❌ Failed to create multi_grn_non_managed_details table")
            sys.exit(1)
        
        # Verify migration
        if not migrator.verify_migration():
            print("\n❌ Verification failed")
            sys.exit(1)
        
        print("\n" + "=" * 70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nChanges made:")
        print("  multi_grn_batches:")
        print("    • Added doc_series_id, doc_series_name")
        print("    • Added QC workflow columns (qc_status, qc_approver_id, qc_reviewed_at, qc_notes)")
        print("    • Added submitted_at, posted_by_id")
        print("\n  multi_grn_line_selections:")
        print("    • Added is_complete, qc_status")
        print("    • Added admin_date, expiry_date")
        print("    • Added qty_per_pack, no_of_packs")
        print("\n  New table:")
        print("    • Created multi_grn_non_managed_details")
        print()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        migrator.close()

if __name__ == "__main__":
    main()
