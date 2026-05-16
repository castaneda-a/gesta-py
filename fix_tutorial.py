import json

with open("gesta_tutorial.ipynb", "r") as f:
    data = json.load(f)

for cell in data["cells"]:
    if "source" in cell:
        new_source = []
        for line in cell["source"]:
            line = line.replace("OfferingType", "OfferingStats") # well, OfferingType is removed
            line = line.replace("appt1.clients", "[p for p in appt1.persons if p.is_recipient]")
            line = line.replace("appt2.clients", "[p for p in appt2.persons if p.is_recipient]")
            line = line.replace("appt1.providers", "[p for p in appt1.persons if p.is_provider]")
            line = line.replace("appt.clients", "[p for p in appt.persons if p.is_recipient]")
            line = line.replace("tx.clients", "[p for p in tx.persons if p.is_recipient]")
            line = line.replace("tx.price_per_client", "tx.price_per_person")
            line = line.replace("offering_id", "service_id")
            line = line.replace("track_inventory", "requires_space")
            line = line.replace("duration_minutes", "duration_min")
            line = line.replace("requires_provider", "requires_space")
            new_source.append(line)
        cell["source"] = new_source

with open("gesta_tutorial.ipynb", "w") as f:
    json.dump(data, f, indent=1)
