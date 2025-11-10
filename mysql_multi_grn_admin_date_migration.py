#!/usr/bin/env python3
"""
MySQL Migration: Add admin_date to Multi GRN Batch and Serial Details
Adds admin_date column to multi_grn_batch_details and multi_grn_serial_details tables
to match GRPO schema structure for QR code label generation.

Run with: python mysql_multi_grn_admin_date_migration.py
"""

import os
import sys
import logging
import pymysql
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiGRNAdminDateMigration:
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
    
    def add_admin_date_columns(self):
        """Add admin_date column to multi_grn_batch_details and multi_grn_serial_details"""
        
        migrations = []
        
        # 1. Add admin_date to multi_grn_batch_details
        migrations.append({
            'name': 'Add admin_date to multi_grn_batch_details',
            'check_sql': """
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'multi_grn_batch_details' 
                AND COLUMN_NAME = 'admin_date'
            """,
            'sql': """
                ALTER TABLE multi_grn_batch_details 
                ADD COLUMN admin_date DATE NULL 
                AFTER expiry_date
            """,
            'backfill_sql': """
                UPDATE multi_grn_batch_details bd
                INNER JOIN multi_grn_line_selections ls ON bd.line_selection_id = ls.id
                SET bd.admin_date = ls.admin_date
                WHERE bd.admin_date IS NULL AND ls.admin_date IS NOT NULL
            """
        })
        
        # 2. Add admin_date to multi_grn_serial_details
        migrations.append({
            'name': 'Add admin_date to multi_grn_serial_details',
            'check_sql': """
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'multi_grn_serial_details' 
                AND COLUMN_NAME = 'admin_date'
            """,
            'sql': """
                ALTER TABLE multi_grn_serial_details 
                ADD COLUMN admin_date DATE NULL 
                AFTER expiry_date
            """,
            'backfill_sql': """
                UPDATE multi_grn_serial_details sd
                INNER JOIN multi_grn_line_selections ls ON sd.line_selection_id = ls.id
                SET sd.admin_date = ls.admin_date
                WHERE sd.admin_date IS NULL AND ls.admin_date IS NOT NULL
            """
        })
        
        # Execute migrations
        success_count = 0
        for migration in migrations:
            try:
                # Check if column already exists
                self.cursor.execute(migration['check_sql'])
                result = self.cursor.fetchone()
                
                if result and result[0] > 0:
                    logger.info(f"⏭️  Skipping '{migration['name']}' - column already exists")
                    success_count += 1
                    continue
                
                # Add column
                logger.info(f"🔧 Executing: {migration['name']}")
                self.cursor.execute(migration['sql'])
                self.connection.commit()
                logger.info(f"✅ {migration['name']} - completed")
                
                # Backfill data if SQL provided
                if 'backfill_sql' in migration:
                    logger.info(f"🔄 Backfilling admin_date from line_selections...")
                    self.cursor.execute(migration['backfill_sql'])
                    affected_rows = self.cursor.rowcount
                    self.connection.commit()
                    logger.info(f"✅ Backfilled {affected_rows} records")
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ Error in {migration['name']}: {e}")
                self.connection.rollback()
                return False
        
        logger.info(f"\n✅ Migration completed successfully! ({success_count}/{len(migrations)} changes applied)")
        return True
    
    def verify_migration(self):
        """Verify that admin_date columns exist"""
        try:
            logger.info("\n📊 Verifying migration...")
            
            tables = ['multi_grn_batch_details', 'multi_grn_serial_details']
            
            for table in tables:
                self.cursor.execute(f"""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = '{table}' 
                    AND COLUMN_NAME = 'admin_date'
                """)
                result = self.cursor.fetchone()
                
                if result:
                    logger.info(f"✅ {table}.admin_date exists: {result[1]} {result[2]}")
                else:
                    logger.error(f"❌ {table}.admin_date NOT FOUND")
                    return False
            
            logger.info("✅ All columns verified successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error verifying migration: {e}")
            return False
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("🔌 Database connection closed")

def main():
    """Main migration execution"""
    print("=" * 60)
    print("Multi GRN Admin Date Migration")
    print("=" * 60)
    print()
    
    migrator = MultiGRNAdminDateMigration()
    
    try:
        # Get database config
        config = migrator.get_database_config()
        
        # Connect to database
        if not migrator.connect(config):
            print("\n❌ Failed to connect to database")
            sys.exit(1)
        
        # Run migrations
        print("\n🚀 Starting migration...\n")
        if not migrator.add_admin_date_columns():
            print("\n❌ Migration failed")
            sys.exit(1)
        
        # Verify migration
        if not migrator.verify_migration():
            print("\n❌ Verification failed")
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("\nChanges made:")
        print("  • Added admin_date column to multi_grn_batch_details")
        print("  • Added admin_date column to multi_grn_serial_details")
        print("  • Backfilled admin_date from line_selections where available")
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
