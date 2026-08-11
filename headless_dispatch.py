import argparse
import importlib
import json
import os
import sys

def main():
    parser = argparse.ArgumentParser(description="Headless render dispatcher")
    parser.add_argument("--scene", required=True, help="Module containing the scene (e.g. instagram_loop)")
    parser.add_argument("--format", default="gif", choices=["gif", "mp4"])
    args = parser.parse_args()
    
    try:
        module = importlib.import_module(args.scene)
        from core.scene import Scene
        scene_class = None
        for name, obj in vars(module).items():
            if isinstance(obj, type) and issubclass(obj, Scene) and obj is not Scene:
                scene_class = obj
                break
                
        if not scene_class:
            raise ValueError("No Scene class found in module")
            
        out_file = f"{args.scene}.{args.format}"
        scene_instance = scene_class(output_file=out_file)
        scene_instance.run()
        
        print(json.dumps({
            "status": "success",
            "file": os.path.abspath(out_file)
        }))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
