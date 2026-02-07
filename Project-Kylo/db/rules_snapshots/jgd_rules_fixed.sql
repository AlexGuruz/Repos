-- JGD Rules from Main Worksheet (PRESERVING FORMAT)
TRUNCATE rules_pending_jgd;

INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('710 PROPERTY TAXES', 'JGD', 'TAXES', True, 'd5858377aa22dd5b8777c3a2dbc297c94d89863167ff0fdda15dba4c63c08aba')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ADVANCE PAYROLL 26871', 'PAYROLL', 'JASON N.', True, '179794064c741872cb11bec0afd935701cdfafc8a52b8fe25603802a03d98f57')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ATM LOAD', 'JGD', 'ATM LOAD', True, 'a42f40aff562977d273701a44269f1e2eb98b92c8709fe7a0ebaa07eaee561bb')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('CHAT GPT', 'JGD', 'GROK AI', True, 'a9deb12c9c79cc4c1f294a4ce330f078fcd3e2292631b68fe74ce208d32c4db2')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('CLEANING', 'JGD', 'SERVICE FEE', True, 'bc6003a0a0c85a8b684246f080bd345a0c9a0d30dddb0547878fd8caf0d2aa2a')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('GROK AI', 'JGD', 'GROK AI', True, 'b5b45fdc7a80ace0ea9b25c341e2da6f8469c7632179b8a3e0899dc4a5d05de1')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('LOS HERMANOS TIRE REPAIR', 'PUFFIN C.O.G.', 'TRACTOR', True, '89c768b75b71d76cb46aa37cdf114e43550d84f53eefc837ad1fe2c98a906d41')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER CITY LIMITS', '(A) CANNABIS DIST.', 'CITY LIMITS', True, '9f77d18ca89d135964deef563b451387c8f17a0614b405fd82446648ef881962')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 26444', 'PAYROLL', 'MYRA N.', True, '111c9693c1ea37b7272af06d26cb30488adce187a1585529a22e9ec9cf294cb5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 26871', 'PAYROLL', 'JASON N.', True, '55ff1d11baf5f52b34000703b528ff8fe8349ceac673cc2bbf696ffd7594bd12')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 31971', 'PAYROLL', 'JENNIFER W.', True, 'ee9daaea2d2c6e6876088bc0f3b38e0568f64ee2e9109618944b1d70f25ab667')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 32040', 'PAYROLL', 'JOHNNY S.', True, '184a1b2094e3e4a71f8874778957e5d5a339edbe6c456e5499541ac64d0a9463')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 32092', 'PAYROLL', 'JIMMY G.', True, 'cfdba1708d119aa1dbd021c18d366107b54f91f2b96b9c2f0476b6eb5bb10d7f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 34210', 'PAYROLL', 'ZACHARY W.', True, 'c4b9db2493d485972e82aace119d2668104d36b03af4b0514ab7a0d12a205fb7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 35851', 'PAYROLL', 'AUSTIN H.', True, '4c3b30bd4683dfbcaf0393bf3b36964c8cd26de8822efdfeb93c8ff4e3cc4364')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 36777', 'PAYROLL', 'JASMYN S.', True, '9082ab97f03278597635b3ab77db42412a2a326cf3422490d55a407eecfd178c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 36809', 'PAYROLL', 'JAYLEN S.', True, '104ccb518f1ae4ad3cbc954a8ac2b40d14e976238a7a951205358e3ffb037e52')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 37432', 'PAYROLL', 'JASON II', True, 'baedf368935136e15a80d2b2c1f39039cbeb8f88b0a723bb8dc75eb63da993a8')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 37766', 'PAYROLL', 'KAIT S.', True, '3a0852ced8dcb51d0f4a221bb336eff6b02c2177041007635ad6c2232c669b89')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 38183', 'PAYROLL', 'ALLISON W.', True, '3458cfdc305bae7aa980ba2f6eb32f6498f69a9ffcb1dea33bc13f42e3f94b44')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 24950', 'PAYROLL', 'GREG W.', True, 'e54e951fb6480d8dfc6368e2d6a42ee111b08540d35da7065f60498c760dcf6f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PURCELL UTILITIES', 'NUGZ EXPENSES', 'UTILITIES', True, '2ea3ee5026ac3afcc489206719f9420d695c2826c46b0c0435ffa643980f59ec')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('STONED PROJECTS', 'INCOME', 'STONED PROJECT', True, '63d9c296bc2c4262bf91101caab926f0740288c5b13d18b001599ae3dc0c050f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('USPS', 'NUGZ C.O.G.', 'MISC.', True, '71975c2f36af4667a9058c7712aef6c97c7e687788570a672832bd74e724511a')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('VENMO', 'INCOME', 'VENMO', True, '8af35be027bc7c7ddabe8bb5c4634cb81320a88535c2cda99ca99e7258f3ace9')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_jgd (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('WALMART', 'PUFFIN C.O.G.', 'WALMART', True, 'd502bcf4b0d6b8434ca6d9ce9fc98a40d15dd2ef7684e9db85065d0179799407')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
