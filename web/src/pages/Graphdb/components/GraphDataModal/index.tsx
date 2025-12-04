import { MODAL_FORMS, REQUIRED_MODAL_FORMS } from "@/constants"
import { useDatabaseEntity } from "@/domains/entities/database-manager"
import { Form, Input, message, Modal, Select, Typography } from "antd" // 新增 Typography 用于显示固定文本
import { useEffect } from "react"

const { Option } = Select
interface IGraphDataModalProps {
  open: boolean
  onClose: () => void
  editId: string | null
  onFinish: () => void
  formatMessage: (key: string) => string
}
const GraphDataModal: React.FC<IGraphDataModalProps> = ({
  open,
  onClose,
  editId,
  onFinish,
  formatMessage,
}) => {
  const [form] = Form.useForm()
  const { getDatabaseDetail, databaseEntity, loadingGetGraphdbById, runCreateGraphdbs, loadingCreateGraphdbs, runUpdateGraphdbs, loadingUpdateGraphdbs } = useDatabaseEntity();

  useEffect(() => {
    if (editId) {
      getDatabaseDetail(editId)
    }
  }, [editId])

  useEffect(() => {
    if (databaseEntity?.databaseDetail) {
      form.setFieldsValue({
        ...databaseEntity?.databaseDetail,
        type: "NEO4J"
      })
    }
  }, [databaseEntity?.databaseDetail])

  const onCancel = () => {
    form.resetFields()
    onClose()
  }

  const onSubmit = () => {
    form.validateFields().then(async (values) => {
      let res: any = {}
      // 提交时强制携带 type: NEO4J，确保后端接收正确类型
      const submitValues = { ...values, type: "NEO4J" }
      
      if (editId) {
        res = await runUpdateGraphdbs({ session_id: editId }, {
          ...databaseEntity?.databaseDetail,
          ...submitValues, // 使用强制后的类型
        })
      } else {
        res = await runCreateGraphdbs(submitValues) // 使用强制后的类型
      }

      if (res?.success) {
        onFinish()
        onCancel()
        message.success(res?.message)
      } else {
        message.error(res?.message)
      }
    })
  }

  const renderDom = (item: string, idx: number) => {
    switch (item) {
      case 'type':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 35 , fontSize: 20}}>
            
            <Typography.Text strong  style={{ fontSize: '20px' }}>NEO4J</Typography.Text>
            <Form.Item name="type" noStyle>
              <Input type="hidden" defaultValue="NEO4J" />
            </Form.Item>
          </div>
        );
      case 'pwd':
        return <Input.Password maxLength={50} placeholder={formatMessage(`database.modal.placeholder${idx}`)} />;
      default:
        return <Input maxLength={50} placeholder={formatMessage(`database.modal.placeholder${idx}`)} />;
    }
  }

  const renderItem = (item: string, idx: number) => {
    const isRequired = REQUIRED_MODAL_FORMS.includes(item) && item !== 'type';
    
    return <Form.Item
      key={idx}
      label={formatMessage(`database.modal.label${idx}`)}
      name={item}
      rules={isRequired ? [{ required: true, message: formatMessage(`database.modal.placeholder${idx}`) }] : []}
    >
      {renderDom(item, idx)}
    </Form.Item>
  }

  return <Modal
    title={<div style={{ fontSize: 20, fontWeight: 600, textAlign: 'center' }}>
      {editId ? formatMessage('database.modal.title2') : formatMessage('database.modal.title1')}
    </div>
    }
    open={open}
    onCancel={onCancel}
    onOk={onSubmit}
    confirmLoading={loadingCreateGraphdbs || loadingUpdateGraphdbs || loadingGetGraphdbById}
  >
    <Form
      form={form}
      layout="vertical"
      initialValues={{
        type: 'NEO4J', // 新建时默认值设为 NEO4J
        host: 'localhost',
        port: '7687',
      }}
    >
      {
        MODAL_FORMS?.map((key: string, idx: number) => renderItem(key, idx))
      }
    </Form>
  </Modal>
}

export default GraphDataModal