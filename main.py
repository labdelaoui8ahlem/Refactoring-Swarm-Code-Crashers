import argparse
import sys
import os
from dotenv import load_dotenv
from utils.logger import log_experiment  

load_dotenv()

def main():
    from utils.logger import log_experiment, ActionType 
    #
    parser = argparse.ArgumentParser()
    parser.add_argument("--target_dir", type=str, required=True)
    args = parser.parse_args()

    if not os.path.exists(args.target_dir):
        print(f"❌ Dossier {args.target_dir} introuvable.")
        sys.exit(1)

    print(f"🚀 DEMARRAGE SUR : {args.target_dir}")
    log_experiment("System", ActionType.STARTUP, f"Target: {args.target_dir}", "INFO", "OK")
    print("✅ MISSION_COMPLETE")

if __name__ == "__main__":
    main()
