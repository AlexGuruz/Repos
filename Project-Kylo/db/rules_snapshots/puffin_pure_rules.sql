-- PUFFIN PURE Rules from Main Worksheet
TRUNCATE rules_pending_puffin_pure;

INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('pure labs', 'PUFFIN C.O.G.', 'TESTING', True, 'b66c8fa0d10860bd4a49d426d85339bda979ca2fcde5d47f537d34d00057b912')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('walmart', 'PUFFIN C.O.G.', 'WALMART', True, '39fe931744c9d8944ccb40a3e8dc267e4035835e5663e5e712a2acd57f073760')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('marijuana waste', 'NUGZ EXPENSES', '(MJ) WASTE', True, '09455084e3c342d4100beb47c4ceef1b64f3fd508fbf32ffcb4c3f05c12a90f5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('facebook marketplace', 'NUGZ C.O.G.', 'FACEBOOK (MP)', True, 'f5303d6a22feae9aa63e491c58ec46956a2817b72fdab4e63b6a01b767e85bf5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 26444', 'PAYROLL', 'MYRA N.', True, '62e8420c3c60d99d3be5dd6d8c5743bd8e0f1ae2a9aaef469072a81731e98434')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('home depot', 'PUFFIN C.O.G.', 'HARDWARE', True, 'c23841614fa34da8d378b7842532c1e4725fea0c93ed40f06685d45693d6f4a0')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('fuel reimbursement', 'PUFFIN C.O.G.', 'FUEL', True, '3ff168c2e6e30d35534ba7765d710d4069f436c5dc65d6564faa489a8dfca7ec')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('wally's green patch', '(B) CANNABIS DIST.', 'WALLY'S GREEN PATCH', True, '922da0c1a5621581c1311da58e5d24c0b57b212adacba77bc8557c3c73d5bacd')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('crystal clear', 'PUFFIN C.O.G.', 'EQUIPMENT', True, '8598bfc50335188db276a47caf4bb431c13bd3ae6b8f2922c1e1ec0e2f751df9')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('amazon', 'PUFFIN C.O.G.', 'AMAZON', True, '3e5a46779c8b4aa6c027578a546803c408d726da77d4f0da8af59c9182f16331')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('bakashi', 'PUFFIN C.O.G.', 'SOIL', True, 'f9948acaaa82477ed7ba88ee33430c8d622ee0f6bccf95b6328e2b7da66e6736')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_puffin_pure (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('puffin pure property tax', 'PUFFIN EXPENSES', 'TAXES', True, '73d520c3de8a15081377c583ff903ccbce862959bcfd588ffbf67eafd80a6ce3')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
