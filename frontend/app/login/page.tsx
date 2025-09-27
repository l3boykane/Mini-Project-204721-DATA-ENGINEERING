'use client';
import { Button, Card, Form, Input, Typography, message } from 'antd';
import { apiJSON } from '@/lib/api';


export default function LoginPage() {
	const [form] = Form.useForm();
	const onFinish = async (values: any) => {
		try {
			await apiJSON('/auth/login', { method: 'POST', body: JSON.stringify(values) });
			message.success('Login success');
			window.location.href = '/';
		} catch (e: any) {
			// console.log('e', e);
			// console.log('e', JSON.parse(e.message));
			message.error(JSON.parse(e.message).detail || 'Login failed');
		}
	};


	return (
		<div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#f5f5f5' }}>
			<Card title="Sign in" style={{ width: 360 }}>
				<Form form={form} layout="vertical" onFinish={onFinish}>
					<Form.Item name="username" label="Username" rules={[{ required: true}]}>
						<Input placeholder="Username" />
					</Form.Item>
					<Form.Item name="password" label="Password" rules={[{ required: true }]}>
						<Input.Password placeholder="••••••••" />
					</Form.Item>
					<Button type="primary" htmlType="submit" block>
						Login
					</Button>
				</Form>
			</Card>
		</div>
	);
}