"""Read-only v2.6 model readiness check. No network calls; never prints secret values."""
from __future__ import annotations
import json
import os
from pathlib import Path
from atlas_conversation_v24 import model_configuration

FIELDS=('ATLAS_LLM_ENABLED','ATLAS_LLM_PROVIDER','OPENAI_API_KEY',
        'ATLAS_LLM_MODEL','ATLAS_LLM_INPUT_USD_PER_1M',
        'ATLAS_LLM_OUTPUT_USD_PER_1M','ATLAS_LLM_BUDGET_DB',
        'ATLAS_LLM_MAX_ESTIMATED_USD_PER_DAY',
        'ATLAS_LLM_MAX_ESTIMATED_USD_PER_CALL','ATLAS_LLM_MAX_CALLS_PER_DAY')


def main():
    config=model_configuration()
    missing=[key for key in FIELDS if key!='ATLAS_LLM_PROVIDER' and not os.getenv(key,'').strip()]
    path=os.getenv('ATLAS_LLM_BUDGET_DB','')
    report={'llm_opted_in':os.getenv('ATLAS_LLM_ENABLED')=='1',
            'model_configuration_status':config['status'],
            'missing_variable_names':missing,
            'budget_db_absolute':bool(path and Path(path).is_absolute()),
            'persistent_storage_verified':False,
            'provider_side_spending_limit_verified':False,
            'paid_calls_made':0,
            'note':'Run in the actual Render service environment. Local Windows values do not reveal Render settings. This check makes no paid calls.'}
    print(json.dumps(report,indent=2))
    return 0 if config['enabled'] else 1

if __name__=='__main__':raise SystemExit(main())
