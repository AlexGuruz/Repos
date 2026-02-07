from __future__ import annotations

from src.gsheets import load_cfg, svc_from_sa, get_sheet_id


def main():
    cfg = load_cfg("config/config.json")
    svc = svc_from_sa(cfg["service_account"])
    sheet_id = get_sheet_id(svc, cfg["bank_id"], cfg["bank_tab"])

    body = {
        "requests": [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "startColumnIndex": cfg["bank_company_col"] - 1,
                        "endColumnIndex": cfg["bank_company_col"],
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_RANGE",
                            "values": [
                                {"userEnteredValue": cfg["bank_validation_range"]}
                            ],
                        },
                        "showCustomUi": True,
                        "strict": True,
                    },
                }
            }
        ]
    }
    svc.spreadsheets().batchUpdate(
        spreadsheetId=cfg["bank_id"], body=body
    ).execute()
    print("Validation applied.")


if __name__ == "__main__":
    main()


