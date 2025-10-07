'use client';
import React, { useEffect, useState, Fragment } from 'react';
import { Button, Card, Upload, UploadProps, message, Table, Row, Col, Breadcrumb, Modal, Spin, Select, Space, Typography, DatePicker } from 'antd';
import { UploadOutlined, DatabaseOutlined, InboxOutlined} from '@ant-design/icons';
import { API_BASE, apiForm } from '@/lib/api';
import type { TableProps } from 'antd';
const { RangePicker } = DatePicker;
import type { Dayjs } from 'dayjs';

type FilterOption = {
  province_id: { value: string; label: React.ReactNode } | 'all';
  district_id: { value: string; label: React.ReactNode } | 'all';
  date_ranger: any;
};

type DataSource = {
	page: number;
	page_size: number;
	total: number;
	all_page: number;
	items: any[]
};

type DataProvince = [{
	province_id: number;
	province_name: string;
	province_name_en: string;
}];


type DataDistrict = {
	district_id: number;
	district_name: string;
	district_name_en: string;
};

export default function Rain() {
	const [open, setOpen] = useState(false);
	const [isLoading, setIsLoading] = useState(false);
	const [orderField, setOrderField] = useState('date');
	const [orderType, setOrderType] = useState('asc');
	const [dataSource, setDataSource] = useState<DataSource>({
		page: 1,
		page_size: 10,
		total: 0,
		all_page: 0,
		items: [],
	});
	const [dataProvince, setDataProvince] = useState<DataProvince[]>([]);
	const [dataDistrict, setDataDistrict] = useState<DataDistrict[]>([]);
	const [filterOption, setFilterOption] = useState<FilterOption>({
		province_id : 'all',
		district_id : 'all',
		date_ranger : null,
	});
	const [page, setPage] = useState(1);
  	const [pageSize, setPageSize] = useState(10);

	const showModal = () => {
		setOpen(true);
	};

	const hideModal = () => {
		setOpen(false);
	};


	async function refresh(p=page, ps=pageSize, order_by=orderField, order_type=orderType, province_id=filterOption.province_id, district_id=filterOption.district_id, date_ranger=filterOption.date_ranger, init: RequestInit = {}) {
		hideModal();
		try {
			setIsLoading(true);
			let date_start = null;
			let date_end = null;
			let dateFilter = '';
			if(date_ranger) {
				let date_ranger_spit = date_ranger.split(',');
				date_start = date_ranger_spit[0];
				date_end = date_ranger_spit[1];
				dateFilter = `&date_start=${date_start}&date_end=${date_end}`;
			}

			const res = await fetch(`${API_BASE}/list_rain?page=${p}&page_size=${ps}&order_by=${order_by}&order_type=${order_type}&province_id=${province_id}&district_id=${district_id}${dateFilter}`, { 
				cache: "no-store",
				credentials: 'include',
				headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
				...init,
			});

			setDataSource(await res.json());
		} catch (e: any) {
			setTimeout(() => {
				setIsLoading(false);
			}, 500);
		} finally {
			setTimeout(() => {
				setIsLoading(false);
			}, 500);
		}
	}

	const onChangeTable: TableProps<any>['onChange'] = (pagination, filters, sorter:any, extra) => {
		if(extra.action == 'sort') {
			if(typeof sorter.order !== 'undefined') {
				setPage(1);
				setOrderField(sorter.field)
				setOrderType((sorter.order == 'descend' ? 'desc' : 'asc'))
			} else {
				setPage(1);
				setOrderField('date')
				setOrderType('asc')
			}
		}

	};

	useEffect(() => {
		refresh();
	}, [page, pageSize, orderField, orderType, filterOption])


	useEffect(() => {
		if(!open) {
			setTimeout(() => {
				setIsLoading(false);
			}, 500);
		}
	}, [open])

	useEffect(() => {
		async function fetchDistrict(province_id = filterOption.province_id, init: RequestInit = {}) {
			try {
				const res = await fetch(`${API_BASE}/list_district?province_id=${province_id}`, { 
					cache: "no-store",
					credentials: 'include',
					headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
					...init,
				});

				const dataOption = await res.json()
				if(dataOption.total > 0) {
					setDataDistrict([{
						value: "all",
						label: "ทั้งหมด (All)",
					}, ...dataOption.items.map((ele:any) => {
						return {
							value: ele.district_id,
							label: ele.district_name + ' (' + ele.district_name_en+ ')',
						}
					})]);
				} else {
					setDataDistrict([]);
				}
			} catch (e: any) {
				setDataDistrict([]);
			}
		}

		fetchDistrict();
	}, [filterOption.province_id])

	useEffect(() => {
		async function fetchProvince(init: RequestInit = {}) {
			try {
				const res = await fetch(`${API_BASE}/list_province`, { 
					cache: "no-store",
					credentials: 'include',
					headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
					...init,
				});

				const dataOption = await res.json()
				

				if(dataOption.total > 0) {
					setDataProvince([{
						value: "all",
						label: "ทั้งหมด (All)",
					}, ...dataOption.items.map((ele:any) => {
						return {
							value: ele.province_id,
							label: ele.province_name + ' (' + ele.province_name_en+ ')',
						}
					})]);
				} else {
					setDataProvince([]);
				}
			} catch (e: any) {
				setDataProvince([]);
			}
		}
		
		fetchProvince();
	}, [])

	const handleChangeProvince = (value:any) => {
		if(value != 'all') {
			setFilterOption({
				province_id : value,
				district_id : 'all',
				date_ranger : filterOption.date_ranger,
			})
		} else {
			setFilterOption({
				province_id : value,
				district_id : filterOption.district_id,
				date_ranger : filterOption.date_ranger,
			})
		}
		setPage(1);
	}

	const handleChangeDistrict = (value:any) => {
		setFilterOption({
			province_id : filterOption.province_id,
			district_id : value,
			date_ranger : filterOption.date_ranger,
		})
		setPage(1);
	}

	const handleChangeDateRange = (dates: [Dayjs, Dayjs], dateStrings: [string, string]) => {
		if(dates) {
			setFilterOption({
				province_id : filterOption.province_id,
				district_id : filterOption.district_id,
				date_ranger : dateStrings[0] + ',' + dateStrings[1],
			})
			setPage(1);
		} else {
			setFilterOption({
				province_id : filterOption.province_id,
				district_id : filterOption.district_id,
				date_ranger : null,
			})
			setPage(1);
		}
	}

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
				setIsLoading(true);
				await apiForm('/upload', fd);
				message.success('Upload Success');
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
			<Breadcrumb className="breadcrumb-design" separator={`>`}
				items={[{ title: 'Home', href: '/', }, { title: 'Rain' }]}
			/>
			<div className="block-content">
				<Row gutter={[16, 16]}>
					<Col span={24} className="text-right">
						<Button type="primary" onClick={showModal}>
							อัปโหลดข้อมูลฝน (Upload Data Rain)
						</Button>
					</Col>
					<Col span={24}>
						<Spin spinning={isLoading} size={`large`}>
							<Card title={<span><DatabaseOutlined /> Rain</span>}>
								
								<Row gutter={[24, 24]}>
									<Col span={24} className="text-right">
										<Space size={`large`}>
											<Space>
												<Typography.Text>ช่วงวันที่ (Date range) : </Typography.Text>
												<RangePicker onChange={handleChangeDateRange}/>
											</Space>

											<Space>
												<Typography.Text>จังหวัด (Province) : </Typography.Text>
												<Select
													showSearch
													filterOption={(input:any, option:any) => (option?.label?.toLowerCase() ?? '').includes(input?.toLowerCase())}
													// defaultValue={{ value: 'all', label: 'ทั้งหมด (All)' }}
													value={filterOption.province_id}
													options={dataProvince}
													style={{ width: 250, textAlign: `left` }}
													onChange={handleChangeProvince}
												/>
											</Space>

											<Space>
												<Typography.Text>อำเภอ (District) : </Typography.Text>
												<Select
													showSearch
													filterOption={(input:any, option:any) => (option?.label?.toLowerCase() ?? '').includes(input?.toLowerCase())}
													// defaultValue={{ value: 'all', label: 'ทั้งหมด (All)' }}
													value={filterOption.district_id}
													options={dataDistrict}
													style={{ width: 350, textAlign: `left` }}
													onChange={handleChangeDistrict}
												/>
											</Space>
											
										</Space>
									</Col>
									<Col span={24}>
										<Table
											rowKey="id"
											dataSource={dataSource.items}
											columns={[
												{ 
													title: 'No.', 
													align:'center', 
													width: 100, 
													render: (value:string, record:any, index:number) => {
														return (((dataSource.page - 1) * dataSource.page_size) + (index + 1)).toLocaleString();
													}
												},
												{ 
													title: 'วันที่ (Date)', 
													align:'center', 
													width: 150, 
													dataIndex: 'date',
													sortDirections: ['ascend', 'descend'],
													sorter: true, defaultSortOrder: 'ascend' 
												},
												{ 
													title: 'จังหวัด (Province)', 
													dataIndex: 'province_name',
													sortDirections: ['ascend', 'descend'],
													sorter: true,
													render: (value:string, record:any) => {
														return record.province_name + ' (' + record.province_name_en + ')'
													} 
												},
												{ 
													title: 'อำเภอ (District)', 
													dataIndex: 'district_name',
													sortDirections: ['ascend', 'descend'],
													width: 400, 
													sorter: true,
													render: (value:string, record:any) => {
														return record.district_name + ' (' + record.district_name_en + ')'
													}
												},
												{ 
													title: 'ปริมาณน้ำฝน (Rainfall)', 
													align:'center', 
													width: 250, 
													dataIndex: 'rain_mm_wmean', 
													sortDirections: ['ascend', 'descend'],
													sorter: true,
													render: (value:number) => {
														if(value != null) {
															return value.toFixed(2)

														} else {
															return 0
														}
													}
												}
											]}
											pagination={{
												simple:true,
												current: dataSource?.page ?? 1,
												pageSize: dataSource?.page_size ?? 10,
												total: dataSource?.total ?? 0,
												showSizeChanger: true,
												showTotal: (total:number) => {
													return `จำนวนทั้งหมด (Total) ${total.toLocaleString()} รายการ (Items)`
												},
												onChange: (p:number, ps:number) => {
													setPage(p);
													setPageSize(ps);
												},
												locale: {items_per_page: "หน้า (Page)"},
											}}
											onChange={onChangeTable}
										/>
									</Col>
								</Row>
									
							</Card>
						</Spin>
					</Col>
				</Row>

				<Modal
					title="อัปโหลดข้อมูลฝน (Upload Data Rain)"
					open={open}
					onOk={hideModal}
					onCancel={hideModal}
					footer={null}
					width={800}
					destroyOnHidden={true}
				>
					<Spin spinning={isLoading} size={`large`}>
						<Upload.Dragger {...uploadNCProps}>
							<p className="ant-upload-drag-icon">
								<UploadOutlined />
							</p>
							<p className="ant-upload-text">คลิกหรือลากไฟล์ไปยังพื้นที่นี้เพื่ออัปโหลด <br></br> Click or drag file to this area to upload</p>
						</Upload.Dragger>
					</Spin>
				</Modal>
			</div>
		</Fragment>
	);
}