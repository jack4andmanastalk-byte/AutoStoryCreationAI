# 銅山郡地誌（尾根野・沢渡）

<!-- asc-world-compilation: profile=prof-gazetteer kind=gazetteer version=ffbe967515aeca4de65a237836e1a9071b6eda3ec21dded5b9b699794266d284 -->

## Regions

### reg-gun

{"description":"尾根野と沢渡を含む山間の郡。","id":"reg-gun","name":"銅山郡","parent_region_id":null,"project_id":"prj-mine","record_type":"region","schema_version":1,"valid_span_id":null}

### reg-oneno

{"description":"閉山した銅山の町。郵便局が一つある。","id":"reg-oneno","name":"尾根野","parent_region_id":"reg-gun","project_id":"prj-mine","record_type":"region","schema_version":1,"valid_span_id":null}

### reg-sawatari

{"description":"麓の駅町。町役場支所と書庫がある。","id":"reg-sawatari","name":"沢渡","parent_region_id":"reg-gun","project_id":"prj-mine","record_type":"region","schema_version":1,"valid_span_id":null}

## Spatial relations

### sp-toge

{"id":"sp-toge","kind":"mountain_pass","project_id":"prj-mine","record_type":"spatial_relation","schema_version":1,"source_region_id":"reg-oneno","target_region_id":"reg-sawatari","travel_days":null,"valid_span_id":"span-15yrs"}

## Culture states

### cs-15yrs

{"attributes":{"practice":"宛名のない保管郵便は三年で焼却、閲覧簿の写しには欄外注記のみ許される"},"content_version":"8448f262d6eea0899ee8495be26b542f1246fe25d20bcc55bce3c63e1cbc5f47","culture_id":"cul-post","id":"cs-15yrs","previous_state_id":"cs-heizan","project_id":"prj-mine","record_type":"culture_state","region_ids":["reg-oneno","reg-sawatari"],"schema_version":1,"valid_span_id":"span-15yrs"}

### cs-heizan

{"attributes":{"practice":"閉山記録の本欄は支所長検印で確定し、坑夫間の手紙は切手を貼らずに託す"},"content_version":"9fb289f55a683a857466bf6cb9f05a933808028ff30f0721018267c3c4422e2b","culture_id":"cul-post","id":"cs-heizan","previous_state_id":null,"project_id":"prj-mine","record_type":"culture_state","region_ids":["reg-oneno","reg-sawatari"],"schema_version":1,"valid_span_id":"span-heizan"}

## Cultures

### cul-post

{"description":"","id":"cul-post","name":"銅山町の郵便と記録の慣行","project_id":"prj-mine","record_type":"culture","schema_version":1}

## Canon

### 宛名のない三通の手紙

{"content":{"id":"F-01","setup":"ch01","summary":"三通の手紙はどれも差出人が同じで、宛名がない","terms":["差出人"]},"content_version":"103a2458e83ae8ca6c25cff3001965583785caaf432b503be30c23b1f5674c86","id":"wcanon-letters","project_id":"prj-mine","record_type":"world_canon_entry","schema_version":1,"scope":{"kind":"region","reference_id":"reg-oneno"},"source":{"artifact":{"artifact_id":"plan-canon-facts.json","media_type":"application/json","path":"runs/att-5eb3ffd445f2404ca3ffa65742c06539-plan/canon/facts.json","producer_run_id":"att-5eb3ffd445f2404ca3ffa65742c06539-plan","sha256":"530742691fdc945cd474756b382d56eeccc76239b6ff695698912249aca930a4"},"json_pointer":"/facts/0","node_id":"node-4e577937dd8046188907958c9e82c19e","revision_id":"rev-5f5c678e61054d6193be2f09716d3466"},"subject":"宛名のない三通の手紙","supersedes_id":null,"valid_span_id":"span-15yrs"}
