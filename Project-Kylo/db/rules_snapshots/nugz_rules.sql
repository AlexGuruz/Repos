-- NUGZ Rules from Main Worksheet
TRUNCATE rules_pending_nugz;

INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('all time resale', 'NON CANNABIS', 'ALL TIME RESALE', False, '97693b54b9c2a46b186fd421bfbd75ec39cf0c9d10ea991e0cd2467866ba09eb')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('atm load', 'JGD', 'ATM LOAD', True, '7dced61382632f0d04c9d9c80bcfba866f2a96831c92906b06f412234e03113e')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('buddies distribution', 'NON CANNABIS', 'BUDDIES DIST.', True, 'd23c27e89bac2e6a6cb265a6a57938f1cad51189a0d8393a8e51ec64a6381b89')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('c - store', 'NON CANNABIS', 'C-STORE', True, 'f2ca793697e75201806b9ad7830d164ea99a74878453d33c3a708136a274f88c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('equipment', 'NUGZ C.O.G.', 'MISC.', True, '34ae75b28d0d020b36f4ebdfc5de0a048be60d6c6dbb3122cee782aca5fae785')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('estimated sales tax', 'NUGZ C.O.G.', 'ESTIMATED TAX', True, '26462cab5b61a208b4e28e6a5b6987c161e42b647d5fa8529ed7641a66f1040e')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('estimated sales tax (apr)', 'NUGZ C.O.G.', 'ESTIMATED TAX', True, '5f93fe14079b8226c869a5e99ed7b053489ed69f5a8400ac549f142709f8b485')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('estimated sales taxes (feb)', 'NUGZ C.O.G.', 'ESTIMATED TAX', True, '7f45853324c3bedb02d2e37a93ea100fb096964e5a4eb77c44b109593a7b3f5b')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('facebook marketplace', 'NUGZ C.O.G.', 'FACEBOOK (MP)', True, 'f5303d6a22feae9aa63e491c58ec46956a2817b72fdab4e63b6a01b767e85bf5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('fire extinguisher inspection', 'NUGZ C.O.G.', 'FIRE SAFETY', True, '318dbbb7f7c76d4cdeb9b864aa420dfb792d4909e32823debc0ae8cdc566ebce')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('fuel reimbursement', 'NUGZ C.O.G.', 'FUEL', True, 'ba1ff78aba9b4c86b7c0f1eddcc2d3c6e166c6b1c2b8457637942d2b352ec6c7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('mj taxes', 'NUGZ C.O.G.', 'MJ TAX', True, '1297fdd64c4f12e7ef35da6e9315847027342bde49b44f6a6f98eab326669907')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('mj taxes (dec)', 'NUGZ C.O.G.', 'MJ TAX', True, '29bb894f06ce83288e4cf1d1361c3c84091b906d551af05a7d145368b1893077')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('mj taxes (jan)', 'NUGZ C.O.G.', 'MJ TAX', True, '242e11bf34ddabff474f52f564b08d11a3b3412aa2ac8acc84825dc722d6dd3f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('mj taxes (mar)', 'NUGZ C.O.G.', 'MJ TAX', True, 'b6f938536a52c1e4860b57730d0f34fc61ca39ca6f2430e06f66488bc8fe7845')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('money drop', 'INCOME', 'REGISTERS', True, '489860bd0872c5f7ccf7ec124ceac57283156dad61a93a8957db97cf7afa4cfa')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('nugz licensing', 'NON CANNABIS', 'OMMA', True, '2d4dd05eaed5b7fe6b04b88deecff0a795b661dc0d0e14fa0d016c8f473a9228')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('nugz sign', 'NUGZ EXPENSES', 'YOUTUBE', True, '3b0fd59c3776525ba555c3ba2fdf0c41580be22ec6edf6f835d499f059fa3733')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('office supplies', 'NUGZ EXPENSES', 'OFFICE SUPPLIES', True, '23e429e5dd9edc40b315f49b35322c756a78bf083fe1f27c4a27f81305aa01c7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order  melania 0224', '(A) CANNABIS DIST.', 'MELANIA 0224', True, 'd51f9eb4eb134d25d2fa77758e05e3dcb7b25d4bfa949eefaf9c32ac6704555f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order 420 my way', 'NON CANNABIS', '420 MY WAY', True, 'ebd9c1447d7e776fd81107d06161ce3ecebc11296ef9ae0f74464add8d6bf0f5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order better with a bang', '(A) CANNABIS DIST.', 'BORO', True, 'c06bafac66c5b271377432a50b51310d88c3c295b10e1ff26098195e52b4e428')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order boro farms', '(A) CANNABIS DIST.', 'FAITH O528', True, 'd0c910c4eabaec231d10ea1200cc7d8044fb39524051835088d996fc20ec79e6')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order cartel', '(A) CANNABIS DIST.', 'CARTEL', True, '4599172dec6aa8af875c88c2273e366b97fbcd78f12ce8d3aede1bbdaf32d87a')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order caviar gold', '(A) CANNABIS DIST.', 'GRAY CLOUD', True, '3f8821c2e9a5c23310047984427d7d4180e45746dd00c0d935de0bb5a3e9f8ab')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order city limits', '(A) CANNABIS DIST.', 'CITY LIMITS', True, '853ec7ae0cb9e7267c6fbabb44d651c1373b89354e3c4bcbdf4c10e3a82bae63')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order country cannabis', '(A) CANNABIS DIST.', 'BIG COUNTRY', True, '9e8c9af0c4c43832086c2afa044138de2d62497b43a4cf6f02f7048b1951daa4')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order cure injoy', '(A) CANNABIS DIST.', 'CURE INJOY', True, '818a70614f19f9688f42aca76cf5ede442fd2e30084e48431d4cc754920e59f7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order dime', '(B) CANNABIS DIST.', 'PARAGON XTR.', True, 'ae9574f35c5f259dba2828cb71e09d7f57cc1c23c46704f06f26df19dcfbf371')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order doc fergusen', '(A) CANNABIS DIST.', 'DOC FERGUSON', True, 'af07ef251c153f111fa3b34567e231142c9a047ea01915fa65bcdbb742695de2')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order easy street', '(A) CANNABIS DIST.', 'EASY STREET', True, 'd4f03336252c6871bf9f630084126b942d481eb6e21e4b811d1584bd8120dc9a')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order for mitchell's novelties', 'ALLOCATED', 'MELVIN', True, '6f2519827e7ad0576b31d18a517f02f644a5e576c1be0bfaea7a74ce4b5c187c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order gladiator farms', '(A) CANNABIS DIST.', 'GLADIATOR', True, 'af7c2c52eaf50ab2dd3a17451679336380864b464dc1515683b7e841e9af5ab2')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order high guys', '(A) CANNABIS DIST.', 'HIGH GUYS', True, 'b43c42de1eeac69597f393536f3d973828a388f3d27cc2e9551ec162954913a1')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order high voltage farms', '(A) CANNABIS DIST.', 'HIGH VOLTAGE', True, '319d3d5d456ccd00e9a21ade37068275c348b93e6a8b63c846d69def8732e1fd')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order mitchell's novelties', 'ALLOCATED', 'MELVIN', True, 'b28335b96a412719bb6b84692a782b804546b5c891368bec19ccde410266fef6')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order molecular extract', '(A) CANNABIS DIST.', 'MOLECULAR', True, '389092b5450ef35b51443783fe8451a6b8b005aa021bdcd8dd5b208cd94212fa')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order molecular extracts', '(A) CANNABIS DIST.', 'MOLECULAR', True, '2cdfb8e1f9971c982bb141f0a550dc91b8dccc169330a0c0084001981643dc66')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order okc novelty', 'NON CANNABIS', 'OKC NOVELTY', True, 'ccc22e44b78f1e1ab233bd83d6b9fbbc5874ba492d8d034c532de89a4e7680cc')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order okie soap shop', 'NON CANNABIS', 'OKIE SOAP SHOP', True, '482587273f165eaf69f8b1ef3df5b6af469a9447f0d5df1c08b29c1845b12851')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order oklahoma dreamin', '(B) CANNABIS DIST.', 'OKLAHOMA DREAMIN', True, '9389a375a6960ba5fc1c20ef62e5503e37f6565001d69f4f20ce199078ac1df4')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order platinum farms', '(B) CANNABIS DIST.', 'PLATINUM FARMS', True, '599f983eb2471371744ca64b8bba4ded56c92a07c2f9bd6764caf2cc34d27398')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order presidential', '(B) CANNABIS DIST.', 'RED HEALTH', True, 'e08b15eb11c4a66f2ab73b483131e4f08aa140effcd778668b7b01de4a16ac3d')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order primal', '(B) CANNABIS DIST.', 'OKIE BOTANICAL', True, '2b5d24a411b4d0fc0a3336a5a3aa6c9969361ecfd007a2a9a31bb9b0fdb1242b')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order sap stix', '(B) CANNABIS DIST.', 'SAP XTRACTS', True, '32ff1e1186a4b6ec6c4acc5204b7936cb6249f6b1a9e768a40ea0dd1a16cd6ea')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order smokiez', '(B) CANNABIS DIST.', 'SMOKIES', True, '91241ad5c17f0a598d2a655b07df97edf7388082dde47355dad6c723d9ce0983')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order sooner wholesale ', 'NON CANNABIS', 'Sooner Wholesale', True, '4f823fa4a6dddb6a337c884b779143e73189bb8a3a1e646b6035206eda94a3df')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order stashhouse', '(B) CANNABIS DIST.', 'STASH HOUSE', True, 'c08f637d6084441e6701d54b1f05ee192dfd905808b3af9da6b8f26316a8da2c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order sunday extracts', '(B) CANNABIS DIST.', 'SUNDAY', True, 'ce86cf4890fe17d9f37c3602218e7abdf08adafc34faf61e6cdb23777382ed5d')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
