'use client';
import React, { useEffect, useState, Fragment } from 'react';
import { Button, Card, Upload, UploadProps, message, Table, Row, Col, Breadcrumb, Modal, Spin } from 'antd';
import { UploadOutlined, DatabaseOutlined, InboxOutlined} from '@ant-design/icons';
import { API_BASE, apiForm, apiJSON } from '../lib/api';




export default function Rain() {
	const [datasets, setDatasets] = useState<any[]>([]);
	const [open, setOpen] = useState(false);
	const [isLoading, setIsLoading] = useState(false);
	const showModal = () => {
		setOpen(true);
	};

	const hideModal = () => {
		setOpen(false);
	};


	async function refresh() {
		hideModal();
		const res = await apiJSON('/datasets');
		setDatasets(res);
	}

	useEffect(() => {
		refresh();
		
	}, [])


	useEffect(() => {
		if(!open) {
			setTimeout(() => {
				setIsLoading(false);
			}, 500);
		}
		
	}, [open])

	const uploadNCProps: UploadProps = {
		name: 'file',
		multiple: false,
		maxCount: 1,
		accept: '.nc',
		customRequest: async (options: any) => {
			const { file, onSuccess, onError } = options;
			try {
				const fd = new FormData();
				fd.append('file', file as File);
				fd.append('note', '');
				setIsLoading(true);
				await apiForm('/upload', fd);
				message.success('NetCDF uploaded');
				await refresh();
				onSuccess?.(null, file);
			} catch (e: any) {
				message.error(e.message || 'Upload failed');
				onError?.(e);
				setIsLoading(false);

			}
		}
	};


	return (
		<Fragment>
			<Breadcrumb className="breadcrumb-design"
				items={[{ title: 'Home', path: '/', }, { title: 'Rain' }]}
			/>
			<div className="block-content">
				<Row gutter={[16, 16]}>
					<Col span={24} align={`right`}>
						<Button type="primary" onClick={showModal}>
							Upload Data Rain
						</Button>
					</Col>
					<Col span={24}>
						<Card title={<span><DatabaseOutlined /> Data Rain</span>}>
							<Table
								rowKey="id"
								dataSource={datasets}
								columns={[
									{ title: 'ID', dataIndex: 'id' },
									{ title: 'Year', dataIndex: 'year' },
									{ title: 'Province', dataIndex: 'province' },
									{ title: 'District', dataIndex: 'district' },
									{ title: 'Latitude', dataIndex: 'lat' },
									{ title: 'Longitude', dataIndex: 'lon' },
									{ title: 'Rainfall', dataIndex: 'rainfall_mm' },
								]}
								pagination={{ pageSize: 10 }}
							/>
						</Card>
					</Col>
				</Row>

				<Modal
					title="Upload Data Rain"
					open={open}
					onOk={hideModal}
					onCancel={hideModal}
					footer={null}
				>
					<Spin spinning={isLoading} size={`large`}>
						<Upload.Dragger {...uploadNCProps}>
							<p className="ant-upload-drag-icon">
								<UploadOutlined />
							</p>
							<p className="ant-upload-text">Click or drag file to this area to upload</p>
						</Upload.Dragger>
					</Spin>
				</Modal>
			</div>
		</Fragment>
	);
}