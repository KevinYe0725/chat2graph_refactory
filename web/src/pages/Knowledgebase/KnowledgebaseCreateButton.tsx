import { Button } from 'antd';
import { useImmer } from 'use-immer';
import { useKnowledgebaseEntity } from '@/domains/entities/knowledgebase-manager';
import useIntlConfig from '@/hooks/useIntlConfig';
import { useEffect } from 'react';
import KnowledgebasesDrawer from '@/pages/KnowledgebaseDetail/components/KnowledgebasesDrawer';
import styles from '@/pages/Home/index.less';
import { ReadOutlined } from '@ant-design/icons';


// 封装全局知识库新建知识按钮组件
const KnowledgebaseCreateButton = () => {
  const [state, setState] = useImmer<{
    open: boolean;
  }>({
    open: false,
  });
  const { open } = state;
  
  const { getKnowledgebaseList, knowledgebaseEntity } = useKnowledgebaseEntity();
  const { formatMessage } = useIntlConfig();

  useEffect(() => {
    // 获取知识库列表以拿到全局知识库信息
    if (!knowledgebaseEntity?.global_knowledge_base?.id) {
      getKnowledgebaseList();
    }
  }, []);

  const globalKnowledgebaseId = knowledgebaseEntity?.global_knowledge_base?.id;

  const handleOpenDrawer = () => {
    setState((draft) => {
      draft.open = true;
    });
  };

  const handleCloseDrawer = (isRefresh?: boolean) => {
    setState((draft) => {
      draft.open = false;
    });
    if (isRefresh) {
      getKnowledgebaseList();
    }
  };

  return (
    <>
      <Button 
        type={'text'}
        className={styles['add-application']}
        size='large'
        icon={<ReadOutlined />}
        onClick={handleOpenDrawer}
      >
        添加知识库文本源
      </Button>

      {globalKnowledgebaseId && (
        <KnowledgebasesDrawer
          open={open}
          onClose={handleCloseDrawer}
          formatMessage={formatMessage}
          id={globalKnowledgebaseId}
        />
      )}
    </>
  );
};

export default KnowledgebaseCreateButton;