from generate_cheat_sheet import generate_cheat_sheet

for co in ["ladders", "tillster", "guidehealth", "hackajob", "ottimate", "ukg"]:
    try:
        generate_cheat_sheet(co)
        print(f"cheat {co} ok")
    except Exception as exc:
        print(f"cheat {co} FAIL: {exc}")
