import traceback
try:
    from main import ResolutionPipeline
    pipeline = ResolutionPipeline()
    res = pipeline.run(workday_csv="data/workday.csv", greenhouse_json="data/greenhouse.json", config_path="config/schema.json", output_path="data/new_output.json")
    print("Done")
except Exception as e:
    traceback.print_exc()
