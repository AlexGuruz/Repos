-- NUGZ Rules from Main Worksheet (PRESERVING FORMAT)
TRUNCATE rules_pending_nugz;

INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ALL TIME RESALE', 'NON CANNABIS', 'ALL TIME RESALE', False, '1a49013caa7bcc2e114bd65af6ba541493826bb1e50fc375a09f746effc070ca')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ATM LOAD', 'JGD', 'ATM LOAD', True, 'a42f40aff562977d273701a44269f1e2eb98b92c8709fe7a0ebaa07eaee561bb')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('BUDDIES DISTRIBUTION', 'NON CANNABIS', 'BUDDIES DIST.', True, 'c3e3e302332327a83e4afc6c9931141944acbb45f6fb0136762fa0abf8d36bb0')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('C - STORE', 'NON CANNABIS', 'C-STORE', True, '763a64e084f071c5195dae571cfa1b4f32a15ef6b85ca717a7da41230605094b')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('EQUIPMENT', 'NUGZ C.O.G.', 'MISC.', True, 'ff31331d6f9b0fc047dab1468e2a89c6597f027fda1e1ae3e7e8a7cfaf8dbecf')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ESTIMATED SALES TAX', 'NUGZ C.O.G.', 'ESTIMATED TAX', True, '5504ff5777b991139343e1fb026b581e0f8ff6973017f3296e531fd16e6b1275')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ESTIMATED SALES TAX (APR)', 'NUGZ C.O.G.', 'ESTIMATED TAX', True, 'b597e6f6f6a3f1e7958f8ac6efb2f0934dbf4d6f6027a12464ea9506d0739df5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ESTIMATED SALES TAXES (FEB)', 'NUGZ C.O.G.', 'ESTIMATED TAX', True, '415532ac0a3a96d45aa379e116c636f1afb9aea5315761f6cd23859a54f1ff19')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('FACEBOOK MARKETPLACE', 'NUGZ C.O.G.', 'FACEBOOK (MP)', True, '937339b21b80a679c99de491b9a8b4a2380b35506f7197182820f91e2900e278')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('FIRE EXTINGUISHER INSPECTION', 'NUGZ C.O.G.', 'FIRE SAFETY', True, '4872cbfd81b2700e2c1fac97fe35a8a4610ea63100627d830bbc44489db70936')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('FUEL REIMBURSEMENT', 'NUGZ C.O.G.', 'FUEL', True, 'c919fbf9cd44571ba45ad2b1d0d624e12ea5efe8eaf25f137543255b6694fae4')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('MJ TAXES', 'NUGZ C.O.G.', 'MJ TAX', True, '4b2b31b5e4b8207675a0b06121be295d05fdbae493da744aa743b03de9a7254d')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('MJ TAXES (DEC)', 'NUGZ C.O.G.', 'MJ TAX', True, '45d68c115101dbd42df751e43b208137bc339b77de46fbc206c1d4b1bb78d4ba')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('MJ TAXES (JAN)', 'NUGZ C.O.G.', 'MJ TAX', True, 'f366c5bc66ecb706ea6cc575f2404de1d50065d98e67a3afb8b40711e4a84b69')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('MJ TAXES (MAR)', 'NUGZ C.O.G.', 'MJ TAX', True, '8cff764f75368bb3813481cade9432b66acf598848c23e37f0724d98271703fc')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('MONEY DROP', 'INCOME', 'REGISTERS', True, '2ecf890ea826eb65e697e58c8a823eba3db55c06608b6b825f21ba0f6b8f6d12')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('NUGZ LICENSING', 'NON CANNABIS', 'OMMA', True, '9dca69af1d7aadb74b356097c695bd1ed2db5acb9ee7f534edba5e1c9feb60aa')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('NUGZ SIGN', 'NUGZ EXPENSES', 'YOUTUBE', True, '10646d1b49a378c66d8b772a7a322d254d817058760b5091c8a8ff0fa7fd1180')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('OFFICE SUPPLIES', 'NUGZ EXPENSES', 'OFFICE SUPPLIES', True, '817630c0504bab7a3c0fad8fcc3968ab09363c36069280746894dcf4f5c14290')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER  MELANIA 0224', '(A) CANNABIS DIST.', 'MELANIA 0224', True, 'bd9bfd3d03fa2a2a743c1c7af104e3d3ad058c3c76e185c0684e19faed3c72d0')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER 420 MY WAY', 'NON CANNABIS', '420 MY WAY', True, 'fd8c5a3b0e5411285134386cac2bbb74acf12c6b45a6e2f589fb9ff3df3388b7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER BETTER WITH A BANG', '(A) CANNABIS DIST.', 'BORO', True, '184387b8dd0a9ce4b6b3e8f8530dc1ff243b794d2a6f16ce2a2d7a0a6b281705')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER BORO FARMS', '(A) CANNABIS DIST.', 'FAITH O528', True, '746315df6868ce523db6239c6bef6e7231154a0d5f04edba69d3c1886e9b2d4e')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER CARTEL', '(A) CANNABIS DIST.', 'CARTEL', True, '8dd844369f8063fbb67c7616d64c1b3c39cae522bac5af0dc75ccdbb0274c8df')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER CAVIAR GOLD', '(A) CANNABIS DIST.', 'GRAY CLOUD', True, 'a824f7b1a124154d735f705e761bbc1d1e89f19080e77cae8e7d5742346f40c6')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER CITY LIMITS', '(A) CANNABIS DIST.', 'CITY LIMITS', True, '9f77d18ca89d135964deef563b451387c8f17a0614b405fd82446648ef881962')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER COUNTRY CANNABIS', '(A) CANNABIS DIST.', 'BIG COUNTRY', True, '317828275143e869cd19f576f7d604e7c090fe5594cf83d9dd2637ed32b4de97')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER CURE INJOY', '(A) CANNABIS DIST.', 'CURE INJOY', True, '9157a535c52ff5367c2b4b2ce53fc3adf6a83feaa7e18fc60ee706c8d9f4ba7b')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER DIME', '(B) CANNABIS DIST.', 'PARAGON XTR.', True, '4a13a8e1a54b40442fee7798f882f33f0d3d465bc984bd8fc80b591fdb8b4541')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER DOC FERGUSEN', '(A) CANNABIS DIST.', 'DOC FERGUSON', True, 'e40a8258481141c7a9021337887e47ce15a5fff9cac3bcd9955281726a672380')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER EASY STREET', '(A) CANNABIS DIST.', 'EASY STREET', True, 'e904cec62f54632c3692ae40653a2c2f03859b067c55c8f51d0c8eb00df4fe49')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER FOR MITCHELL''S NOVELTIES', 'ALLOCATED', 'MELVIN', True, '50dee6d72420b106ca7df34c74bb304e89bef86203deb0eba0e8ba69af41e782')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER GLADIATOR FARMS', '(A) CANNABIS DIST.', 'GLADIATOR', True, '4efc328223952abe250cfcb7d363d48094c560809dfcbf20143fe32687920b4e')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER HIGH GUYS', '(A) CANNABIS DIST.', 'HIGH GUYS', True, '8498a7367db7295c4acdb73c499b71f4dcf0f2015d536ccf6433474086acd05b')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER HIGH VOLTAGE FARMS', '(A) CANNABIS DIST.', 'HIGH VOLTAGE', True, '6d952b10983903aa9d311b074d6f090a577aede900afc369e9854d386138f69d')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER MITCHELL''S NOVELTIES', 'ALLOCATED', 'MELVIN', True, '4977e31fd6e06f8adbf73cce505fd5c71c1674407163f5cd1c7bc44860d1fc67')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER MOLECULAR EXTRACT', '(A) CANNABIS DIST.', 'MOLECULAR', True, '01bd11307916bb2ef93fb5ca005e38f80c68bcc011891e26472381158cf401cd')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER MOLECULAR EXTRACTS', '(A) CANNABIS DIST.', 'MOLECULAR', True, 'b6a4f76131f44ccf8db045a4517470ead2849a442bb17bdbacb740d84be1df0f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER OKC NOVELTY', 'NON CANNABIS', 'OKC NOVELTY', True, 'fe71b6efcb141ea3aeaa6d42b36bd1634b3381f679778373aefa4766766222a8')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER OKIE SOAP SHOP', 'NON CANNABIS', 'OKIE SOAP SHOP', True, '949ad984b7573025e4fa239e7a70806a768b66e9f4cbea47b23c85c8f64cf0b1')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER OKLAHOMA DREAMIN', '(B) CANNABIS DIST.', 'OKLAHOMA DREAMIN', True, '0de4f57a624e0b28c30ba74a9d3f8d1a8a29971c7d22cb32daa5e167ac9c9438')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER PLATINUM FARMS', '(B) CANNABIS DIST.', 'PLATINUM FARMS', True, '9f1d5a11f8c46444e91d422e7d189a3eb49e8d4109d1b7d0bbca4d4d7edf4d13')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER PRESIDENTIAL', '(B) CANNABIS DIST.', 'RED HEALTH', True, '273fef341e458ed6b198c2d72d13c7949a789dc8979787db1d832fefa592a8c9')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER PRIMAL', '(B) CANNABIS DIST.', 'OKIE BOTANICAL', True, '3853d8d11d7be485c694aa7b8592b3c203042846e463c776df7ed860a7775aed')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER SAP STIX', '(B) CANNABIS DIST.', 'SAP XTRACTS', True, 'a513ed393742e6da5043cfd81a830aefa483a58cdb8b08edc2502e68018bf234')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER SMOKIEZ', '(B) CANNABIS DIST.', 'SMOKIES', True, 'b49d720c0d39ed1aab82844aaa7d8fc9041c08e8a9b3334439efb0a51ec3ef62')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER SOONER WHOLESALE ', 'NON CANNABIS', 'Sooner Wholesale', True, 'c3b436f5f8727910bf939107440afa4b92765f4a499f81528b73f9a71194538a')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER STASHHOUSE', '(B) CANNABIS DIST.', 'STASH HOUSE', True, '666a7c9aa2f4c28eeeb2a2f626f96cf5e07bbbcccf27e8f49fbfae963accba50')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER SUNDAY EXTRACTS', '(B) CANNABIS DIST.', 'SUNDAY', True, '320a935beecad8d2c3c878c7fa19f56369bc6a18b5466b8d137b35bc0d88115c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER TERP TALK', '(A) CANNABIS DIST.', 'MELANIA 0224', True, '7f29d26dc5146bdd4af415b20c8b944ec8d4b0b76d22b572c2babe6faa95eff3')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER TIMELESS', '(A) CANNABIS DIST.', 'CROSSFIELD COL.', True, '46b4aa694e6354aa614e31fd910fbc614a131cac9c9d87db8ed495a706167439')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER TRIBE', '(B) CANNABIS DIST.', 'TRIBE', True, 'c9dc236c130503c84e8dfada14e6536e361227a0c19866a91e4c48db93f41bb9')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER VERY GOOD GROW', '(B) CANNABIS DIST.', 'VERY GOOD GROWS', True, 'da95ab98c8d41612cb43dffc4886ecfb0ac30d6c8e2c121718570aa0eb3fbd25')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER WATERCOLOR LABS', '(B) CANNABIS DIST.', 'WATERCOLOR LABS', True, '2ea84806805b49f7d696e8f6dfe12bd949f3835469f7aa1958d1a73c2adfd1d7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER XEN EXTRACTS', '(B) CANNABIS DIST.', 'XEN XTRACTS', True, 'e474e81da01f8820de552c06d1489343594bf8ad7d9a05b694c6c0a9f9f5f9fd')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('ORDER ZEN CANNABIS', '(B) CANNABIS DIST.', 'ZEN CANNABIS', True, '7fb261ea5463fe20d531190a001dbeca480c85544d40ddc730b1ae46d23b2d0c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 24950', 'PAYROLL', 'GREG W.', True, 'e54e951fb6480d8dfc6368e2d6a42ee111b08540d35da7065f60498c760dcf6f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 31971', 'PAYROLL', 'JENNIFER W.', True, 'ee9daaea2d2c6e6876088bc0f3b38e0568f64ee2e9109618944b1d70f25ab667')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 32040', 'PAYROLL', 'JOHNNY S.', True, '184a1b2094e3e4a71f8874778957e5d5a339edbe6c456e5499541ac64d0a9463')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 34210', 'PAYROLL', 'ZACHARY W.', True, 'c4b9db2493d485972e82aace119d2668104d36b03af4b0514ab7a0d12a205fb7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 36777', 'PAYROLL', 'JASMYN S.', True, '9082ab97f03278597635b3ab77db42412a2a326cf3422490d55a407eecfd178c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 36809', 'PAYROLL', 'JAYLEN S.', True, '104ccb518f1ae4ad3cbc954a8ac2b40d14e976238a7a951205358e3ffb037e52')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 37766', 'PAYROLL', 'KAIT S.', True, '3a0852ced8dcb51d0f4a221bb336eff6b02c2177041007635ad6c2232c669b89')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PAYROLL 38183', 'PAYROLL', 'ALLISON W.', True, '3458cfdc305bae7aa980ba2f6eb32f6498f69a9ffcb1dea33bc13f42e3f94b44')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PURCELL UTILITIES', 'NUGZ EXPENSES', 'UTILITIES', True, '2ea3ee5026ac3afcc489206719f9420d695c2826c46b0c0435ffa643980f59ec')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('PURE LABS', 'PUFFIN C.O.G.', 'TESTING', True, '74df8064e5755d76b0689b318a40739f1aa0b6ee08851c2e38cc1776693481f5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('REG 1 BANK', 'INCOME', 'REGISTERS', True, 'dd168c79b654350b091ef921a68a02da6d4acac4a11a28968acea960c692595d')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('REG 1 DEPOSIT', 'INCOME', 'REGISTERS', True, '997e57481e06ae0b98d3d0d7694dc45c270a09c13a6f29bee094d347e82ec0b8')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('REG 2 BANK', 'INCOME', 'REGISTERS', True, '63aed50b9d1ff84162b3ab32f84f8fbf13e2e7bd01b41eca2d1fe339047256b5')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('REG 2 DEPOSIT', 'INCOME', 'REGISTERS', True, 'c14504738cffa40734085649d7a86ef0f43e112055c95fb1e62a272478affc1c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('REG 3 BANK', 'INCOME', 'REGISTERS', True, '6f13fefedb0506df360ab99e6890488113f3c78a8fd3ba8d72ce54c9de133702')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('REG 3 DEPOSIT', 'INCOME', 'REGISTERS', True, '89d796d02095f75517c043d37bf22b4204bc4cf2c7954ffb83ed131b6117c972')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('RETURN ON HOURS', 'INCOME', 'STONED PROJECT', True, '971409ef7387b18008f853c60009ea1ddfcd2da53ade0af57a11149a3422ac10')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO BUD N MORE', 'INCOME', '(N) WHOLESALE', True, '6f1732678966e2ef7b29c90bcf2932faf7aae76c4774786c64d312011eecaa51')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO BUDS N MORE', 'INCOME', '(N) WHOLESALE', True, '7101158110512fe7bb17f59f4a382c2d5883622d4fe55d34aa987be54f8a62b1')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO CHARLIE AND WEED FACTORY', 'INCOME', '(N) WHOLESALE', True, '833335abf627c1df793ac78bd22aebacce793ad723c34cc969e6158a63950d79')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO FAERIE FIRE', 'INCOME', '(N) WHOLESALE', True, '08cd714b521dd9d3cfb63a70416549557143970b9ed93e5e2139d5c6c0da2d41')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO FAERIE FIRE (ZAC)', 'INCOME', '(N) WHOLESALE', True, 'f94437075a165641be746751d3f1dfc1fe7c79065180e080dcb1147468a9fd2d')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO GLADIATOR FARMS', 'INCOME', '(N) WHOLESALE', True, 'b420fe1b1455b0a1fc2a62b3749f81804895b740721f1db129b1533ed2a69ea7')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO GREENER LEAF', 'INCOME', '(N) WHOLESALE', True, '3f8870b408eef8d5985e1755a455a35d5c37defc6f8ffe549faa09e1bc667ae1')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO HIGH HOUSE', 'INCOME', '(N) WHOLESALE', True, 'df5b4e2752476cde3b7177209ddb2102d3cbc27882845d947e9ccfa1c5e06aa1')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO HIGH HOUSE MARIJUANA DISPENSARY', 'INCOME', '(N) WHOLESALE', True, '220bf854278dbdc108edad73fe0c9fcece2f3c034547367e03856edad829da7b')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO LAUGHING HYENA', 'INCOME', '(N) WHOLESALE', True, '255aae27fbcc0aacb92f1c386338ef1f24048968e3d69d5af4bee9f73a4a26fe')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO OKIE EMERALDS', 'INCOME', '(N) WHOLESALE', True, 'be25b66f3f8fe8e8a05a63906e773a95898adb4e75166784846dd2c7f422b659')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO OKIE EMERALDS (ZAC)', 'INCOME', '(N) WHOLESALE', True, 'dbb8c80272e18edea2002c32b32f87ce4ad47db99e278bce9ef273e5362bb494')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO ORGANIC MEDS', 'INCOME', '(N) WHOLESALE', True, '884cf40fc54d587ffc808b781591e058b2ff1c21068e254f621e6bb83b62d95c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO PURE WELLNESS', 'INCOME', '(N) WHOLESALE', True, '89589384238876382fa7129308682128eaba203879c24593978e3c88d3603bea')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO PURE WELLNESS MEDICAL', 'INCOME', '(N) WHOLESALE', True, 'aba20ddc6b7357662cdb3688e4a5625f6373b10d66d41778201009e23ca0faf3')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO SWEET RELEAF', 'INCOME', '(N) WHOLESALE', True, '5d91974d890871ed3430d4b44f2c08438b4c3140dc55e25fd6b9ec508d9c756d')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO TEN HIPPIES', 'INCOME', '(N) WHOLESALE', True, 'f79fde19dc80c91217258bf3e6cc47f33277ad16bf566295dfcae08edf09eab0')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALE TO THE LAUGHING HYENA', 'INCOME', '(N) WHOLESALE', True, 'ae9752b3b2f8b7dd30858aef7f1006cce9d61e4383211ebe0bab604839b90b22')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALES TAX', 'NUGZ C.O.G.', 'SALES TAX', True, 'a6882ceeee206c47abb3319c06f5edb13b7b9afcf6328e6825519f58bd9f35c8')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALES TAX (DEC)', 'NUGZ C.O.G.', 'SALES TAX', True, '4a309a0d909604489ce920523dda8305e9709ae4072cb0731fb33ccd4641d6ab')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALES TAXES (JAN)', 'NUGZ C.O.G.', 'SALES TAX', True, '5acd1da86e2c3c9fa54f99bdd364bf5d522f738b11d344d9d7d2d801ac4500be')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALES TAXES (MAR)', 'NUGZ C.O.G.', 'SALES TAX', True, '3d9d0a48280b7231b7f2eaa6682f8b6cf017cc2e14571b62785b33c2a9cd03eb')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALES TO GREEN''ER LEAF WELLNESS', 'INCOME', '(N) WHOLESALE', True, 'cb666820cad8f487e7f3cec93ebec2648355c4424e7771382207e3621d9a9f06')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SALES TO OKIE EMERALDS', 'INCOME', '(N) WHOLESALE', True, '4f72c93a06f63d4a10657e03a0de45f2533f0e3e270abcd53b236e4951a5060c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('SQUARE TIPS', 'INCOME', 'SQUARE', True, '3fa736b5ba0ae956bf4b4cc99235f443456c96aea41fce2f0393a232f875bafd')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('STONED PROJECTS', 'INCOME', 'STONED PROJECT', True, '63d9c296bc2c4262bf91101caab926f0740288c5b13d18b001599ae3dc0c050f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('TESLA SERVICE', 'PUFFIN EXPENSES', 'TESLA', True, '26a64db4ca17d6e50b2b923c3c301c01574019cc59b1e50dda73c8f299e40d3c')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('TIM', 'INCOME', 'STONED PROJECT', True, 'f8b6145eb217f0f3595859ab6788f107f39ad9d211744cc2a107ad03e399c0cb')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('TIM REIMBURSEMENT', 'INCOME', 'STONED PROJECT', True, '17869132430bf7b7432cc49ee916a022577c478e6e2b47a8d6832122808e1cc2')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('TIM''S REIMBURSMENT', 'INCOME', 'STONED PROJECT', True, 'a4856f5993342234201b8d63879d1339a32476dfae296e53fa670f91af0e18fd')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('TRIFECTA', 'NON CANNABIS', 'TRIFECTA', True, 'd43a54acdc45ff3397284383603df3b6ac83dec7b2e1e8ede7f766189186c761')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('WALMART', 'NUGZ C.O.G.', 'WALMART', True, 'dc84340e017076ea96e267ca58b033e517a84d35eb9767c6429a4fce87a82e1f')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;
