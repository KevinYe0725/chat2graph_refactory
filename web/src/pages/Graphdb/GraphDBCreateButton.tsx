import { Button } from 'antd';
import { useImmer } from 'use-immer';
import GraphDataModal from './components/GraphDataModal';
import { useDatabaseEntity } from '@/domains/entities/database-manager';
import useIntlConfig from '@/hooks/useIntlConfig';
import styles from '@/pages/Home/index.less';
import { DatabaseOutlined } from '@ant-design/icons';

// 封装新建图数据库按钮组件
const GraphDBCreateButton = () => {
  const [state, setState] = useImmer<{
    open: boolean;
  }>({
    open: false,
  });
  const { open } = state;
  
  const { getDatabaseList } = useDatabaseEntity();
  const { formatMessage } = useIntlConfig();

  // 打开新建模态框
  const handleOpenModal = () => {
    setState((draft) => {
      draft.open = true;
    });
  };

  // 关闭模态框
  const handleCloseModal = () => {
    setState((draft) => {
      draft.open = false;
    });
  };

  // 新建完成后刷新数据
  const handleFinish = () => {
    getDatabaseList(); // 刷新数据库列表
    handleCloseModal(); // 关闭模态框
  };

  return (
    <>
      {/* 新建按钮 - 使用固定文本"新建图数据库" */}
      <Button 
        type={'text'}
        className={styles['add-application']}
        size='large'
        icon={<DatabaseOutlined />}
        onClick={handleOpenModal}
      >
        配置图数据库信息
      </Button>

      <GraphDataModal
        editId={null}
        open={open}
        onClose={handleCloseModal}
        onFinish={handleFinish}
        formatMessage={formatMessage}
      />
    </>
  );
};

export default GraphDBCreateButton;
    