'use client';
import React, { useEffect, useState, Fragment } from 'react';
import { Layout, Menu, Button, Card, Upload, UploadProps, message, Table, Typography, Space, Input, Breadcrumb } from 'antd';
import { UploadOutlined, DatabaseOutlined, FileExcelOutlined, LogoutOutlined } from '@ant-design/icons';
import { API_BASE, apiForm } from '../lib/api';


const { Header, Content } = Layout;


export default function Rain() {
	const [datasets, setDatasets] = useState<any[]>([]);
	const [stats, setStats] = useState<any[]>([]);


	async function guard() {
		const res = await fetch(`${API_BASE}/me`, { credentials: 'include' });
		if (res.status === 401) {
			window.location.href = '/login';
		}
	}


	async function refresh() {
		const [a, b] = await Promise.all([
			fetch(`${API_BASE}/datasets`, { credentials: 'include' }),
			fetch(`${API_BASE}/stats`, { credentials: 'include' }),
		]);
		if (a.status === 401 || b.status === 401) { window.location.href = '/login'; return; }
		setDatasets(await a.json());
		setStats(await b.json());
	}


	useEffect(() => { guard().then(refresh); }, []);


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
				
				await apiForm('/upload', fd);
				message.success('NetCDF uploaded');
				await refresh();
				onSuccess?.(null, file);
			} catch (e: any) {
				message.error(e.message || 'Upload failed');
				onError?.(e);
			}
		}
	};


	const uploadStatsProps: UploadProps = {
		name: 'file',
		multiple: false,
		maxCount: 1,
		accept: '.csv,.xlsx,.xls',
		customRequest: async (options: any) => {
		const { file, onSuccess, onError } = options;
			try {
				const fd = new FormData();
				fd.append('file', file as File);
				await apiForm('/upload-stats', fd);
				message.success('Stats uploaded');
				await refresh();
				onSuccess?.(null, file);
			} catch (e: any) {
				message.error(e.message || 'Upload failed');
				onError?.(e);
			}
		}
	};

	async function onLogout() {
		await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
		window.location.href = '/login';
	}

	return (
		<Fragment>
			<Breadcrumb className="breadcrumb-design"
				items={[{ title: 'Home', path: '/', }, { title: 'Rain' }]}
			/>
			<div className="block-content">
				<Card title={<span><UploadOutlined /> Upload NetCDF (.nc)</span>}>
					<Upload {...uploadNCProps}>
						<Button type="primary" icon={<UploadOutlined />}>Select .nc file</Button>
					</Upload>
				</Card>


				<Card title={<span><FileExcelOutlined /> Upload Stats (.csv/.xlsx)</span>}>
					<Upload {...uploadStatsProps}>
						<Button type="primary" icon={<UploadOutlined />}>Select .csv/.xlsx</Button>
					</Upload>
				</Card>

				<Card title={<span><DatabaseOutlined /> Datasets (.nc)</span>}>
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

				<Card title={<span><DatabaseOutlined /> Stats Files (.csv/.xlsx)</span>}>
					<Table
						rowKey="id"
						dataSource={stats}
						expandable={{
							expandedRowRender: (record) => (
								<pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(record.preview, null, 2)}</pre>
							)
						}}
						columns={[
							{ title: 'ID', dataIndex: 'id' },
							{ title: 'Filename', dataIndex: 'filename' },
							{ title: 'Size (MB)', render: (_: any, r: any) => (r.size_bytes/1_000_000).toFixed(2) },
							{ title: 'Rows', dataIndex: 'rows' },
							{ title: 'Cols', dataIndex: 'cols' },
							{ title: 'Content Type', dataIndex: 'content_type' }
						]}
						pagination={{ pageSize: 10 }}
					/>
				</Card>
			</div>
		</Fragment>
	);
}