import { IKnowledgeBase } from '../../interfaces/database/knowledge';
import { IResponse } from '../../interfaces/response';
import { get } from '../../utils/axios';

export const getKnowledgeBase = (sessionId: string) => {
  return get<IResponse<IKnowledgeBase>>(
    `/chat/sessions/${sessionId}/knowledgebase`,
  );
};
