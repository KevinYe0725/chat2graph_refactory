DYNAMIC_WORKFLOW_PROMPT = """

"""
# Example：
# <decomposition>
# {
#   "workflow": {
#     "operators": [
#       {
#         "id": "op1",
#         "name": "retrieve_knowledge",
#         "task": "根据用户任务检索相关信息。",
#         "next": ["op2"]
#       },
#       {
#         "id": "op2",
#         "name": "summarize",
#         "task": "对检索信息进行摘要。",
#         "next": ["op3"]
#       },
#       {
#         "id": "op3",
#         "name": "answer",
#         "task": "根据摘要生成最终答案。",
#         "next": []
#       }
#     ],
#     "evaluator": {
#       "id": "eval1"
#       "task": "根据当前任务goal，和下个任务输入，认为当前输入是否符合标准"
#     }
#   }
# }
# </decomposition>