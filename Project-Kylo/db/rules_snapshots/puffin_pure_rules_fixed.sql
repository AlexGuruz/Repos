-- PUFFIN PURE Rules from Main Worksheet (PRESERVING FORMAT)
TRUNCATE rules_pending_puffin;

INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PURE LABS', 'PUFFIN C.O.G.', 'TESTING', True, '74df8064e5755d76b0689b318a40739f1aa0b6ee08851c2e38cc1776693481f5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('WALMART', 'PUFFIN C.O.G.', 'WALMART', True, 'd502bcf4b0d6b8434ca6d9ce9fc98a40d15dd2ef7684e9db85065d0179799407')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('MARIJUANA WASTE', 'NUGZ EXPENSES', '(MJ) WASTE', True, '362cc55af039b8513a693e635e6c8c82b3457b71cb61778dc7d722f62336eea7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('FACEBOOK MARKETPLACE', 'NUGZ C.O.G.', 'FACEBOOK (MP)', True, '937339b21b80a679c99de491b9a8b4a2380b35506f7197182820f91e2900e278')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 26444', 'PAYROLL', 'MYRA N.', True, '111c9693c1ea37b7272af06d26cb30488adce187a1585529a22e9ec9cf294cb5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('HOME DEPOT', 'PUFFIN C.O.G.', 'HARDWARE', True, '9ff8263edc1805e3e89517ed939e820e18b71b7d5506cd099d52092fa84a2da2')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('FUEL REIMBURSEMENT', 'PUFFIN C.O.G.', 'FUEL', True, '21c780dda3fa81f7d37db92de1fe29984dd13ffbbdc41ddee33369b902e84828')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('WALLY''S GREEN PATCH', '(B) CANNABIS DIST.', 'WALLY''S GREEN PATCH', True, 'd3f9e3cc7ee857fd375dbc1d7e0811aa9627de242993881f874c9f9085430ede')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('CRYSTAL CLEAR', 'PUFFIN C.O.G.', 'EQUIPMENT', True, '2399dd4f5779f117aab4ff6c71069d7864c5e439b92f91dee8ac03b92c25d9a7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('AMAZON', 'PUFFIN C.O.G.', 'AMAZON', True, '42c587c2e1ee1a05bbc674aec2258eba1a63dcc383b45f0f6e8c214493590e09')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('BAKASHI', 'PUFFIN C.O.G.', 'SOIL', True, '8420ce9b6955266822df9a1d349817a936c0a611f0f7f2c7515db2e27ef0f9bf')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PUFFIN PURE PROPERTY TAX', 'PUFFIN EXPENSES', 'TAXES', True, '643653b82813d55e98f1369f766929d89fe7c31bc3cd0cf82284af593a16ef64')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
