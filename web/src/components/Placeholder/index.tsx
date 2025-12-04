import useIntlConfig from '@/hooks/useIntlConfig';
import { Welcome } from '@ant-design/x';
import { Space } from 'antd';

import React from 'react';
import logoSrc from '@/assets/logo.png';
import styles from './index.less';

interface Props {
  placeholderPromptsItems: any[];
  onPromptsItemClick: () => void;
};

const Placeholder: React.FC<Props> = (props) => {
  const { placeholderPromptsItems, onPromptsItemClick } = props;
  const { formatMessage } = useIntlConfig();
  return <div className={styles.placeholder}>
    <img src={logoSrc} width={40} style={{ marginRight: 8 ,border: '2px solid #ffffff', // 这里设置边框
        borderRadius: 8 }} />
    <Space direction="vertical" size={16} style={{ marginBottom: 120 }}>
      <Welcome
        title={formatMessage('home.title')}
        description={formatMessage('home.description')}
      />

    </Space>
  </div>

};

export default Placeholder