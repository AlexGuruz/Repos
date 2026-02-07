-- JGD Rules from Main Worksheet
TRUNCATE rules_pending_jgd;

INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('710 property taxes', 'JGD', 'TAXES', True, '01515010ab55bf1259c4ab910a06592193527b2aaaf751e88e733f1eb1b7d0dd')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('advance payroll 26871', 'PAYROLL', 'JASON N.', True, '6f93dd127da5f561c7ec5ba183329f0452bf04f3e85d6209cd10a707aa530823')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('atm load', 'JGD', 'ATM LOAD', True, '7dced61382632f0d04c9d9c80bcfba866f2a96831c92906b06f412234e03113e')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('chat gpt', 'JGD', 'GROK AI', True, '1b82e23d8b0c538bfd3624720741d591c204380c8361ebb4040e7646e938a9c4')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('cleaning', 'JGD', 'SERVICE FEE', True, '001890e0e04189d2b826705ea605026e331dcbebbd27affded28957bd70ef0ae')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('grok ai', 'JGD', 'GROK AI', True, 'a94252f1e33bbed6be39a58474ea66ac2ff1188bb2644b31f1f0a0f29d78cd65')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('los hermanos tire repair', 'PUFFIN C.O.G.', 'TRACTOR', True, '8e03aecc7b6d28443f58a9f7a15913fdc37d65076325e4d7dbada4f2f47f94d3')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('order city limits', '(A) CANNABIS DIST.', 'CITY LIMITS', True, '853ec7ae0cb9e7267c6fbabb44d651c1373b89354e3c4bcbdf4c10e3a82bae63')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 26444', 'PAYROLL', 'MYRA N.', True, '62e8420c3c60d99d3be5dd6d8c5743bd8e0f1ae2a9aaef469072a81731e98434')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 26871', 'PAYROLL', 'JASON N.', True, 'db8ab4ffd214f75c6caf9296fa8b0b8263e59ea634a4f2c0e6588b48e5d43c83')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 31971', 'PAYROLL', 'JENNIFER W.', True, '51e72f38c9919fec3bef2ec52e6f1fe8a68ec333b046af9a0db186a2e5458136')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 32040', 'PAYROLL', 'JOHNNY S.', True, 'd952a5cd3cbcb19bd44da8e01bc668940b3a72f32aea13c8b616a58161844010')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 32092', 'PAYROLL', 'JIMMY G.', True, 'c64f4f703a08b46bbdfc1926ddf28826e547af660bd6bba071ca4295729f1ff9')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 34210', 'PAYROLL', 'ZACHARY W.', True, '0382fd3ff1efb1b3fbb2697aed80f6612a9e21893a6a629012d2d46fe16eaf3c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 35851', 'PAYROLL', 'AUSTIN H.', True, '8b305d3737c905cf5b1cd4458d8f937b05644bed98894afd671738ce357be67a')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 36777', 'PAYROLL', 'JASMYN S.', True, 'f7148499487c2e293829e1a1a39a1e8118019ab46de61e2d1d3f3b9a7ee7111d')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 36809', 'PAYROLL', 'JAYLEN S.', True, 'a32082f977d6063e383c3a521b4c1cee2c078cb3e6794e28f58031372c5bedc9')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 37432', 'PAYROLL', 'JASON II', True, 'a44c7bec4b976ef728fdc72c7f8ce867f887757b6072291b1542b0dbec1a8863')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 37766', 'PAYROLL', 'KAIT S.', True, 'd39b3f24afddef8752edb035ced32bada8d5be69471d0e6a00188c2e9afa2a90')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 38183', 'PAYROLL', 'ALLISON W.', True, 'aae788e5de376bed81d0e455eb7683c314cd4037ef52db8de09cd69c5680c328')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('payroll 24950', 'PAYROLL', 'GREG W.', True, '5013aec05fc29a19c16deff59687718024ac139ebf32d1c9bcb1e32d03dbc71e')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('purcell utilities', 'NUGZ EXPENSES', 'UTILITIES', True, '935451876704e2dd14c3b71e726087ce11bcf4072db8959a4fedd0590cb2ce73')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('stoned projects', 'INCOME', 'STONED PROJECT', True, '22828f1c8fe27f05f97d37b4eb0ece9ee31e722174a145f380210fef4565804b')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('usps', 'NUGZ C.O.G.', 'MISC.', True, '9568186aa96b7ec6b43c39c8a3bafe19343c4ae20db3531c9294038a7b707e82')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('venmo', 'INCOME', 'VENMO', True, '6b5f1dd145b68e7fd401a3d350e7a5d274da5132a5791ef5c759721a40c8ba8a')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('walmart', 'PUFFIN C.O.G.', 'WALMART', True, '39fe931744c9d8944ccb40a3e8dc267e4035835e5663e5e712a2acd57f073760')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
