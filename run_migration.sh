#!/bin/bash
# Run migration script

V1_URL="postgresql://postgres:vets_secure_pw@host.docker.internal:5432/dva_db"
V2_URL="postgresql://postgres:vets_secure_pw@host.docker.internal:5433/dva_db"

docker exec dva-scraper-v2 python migrate_from_v1.py --v1-url "$V1_URL" --v2-url "$V2_URL" --batch-size 50
